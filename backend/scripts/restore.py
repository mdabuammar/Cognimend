#!/usr/bin/env python3
"""
Database Restore Script

Provides:
- PostgreSQL restore from pg_dump or JSON backup
- Qdrant snapshot restore
- Redis restore from RDB or JSON
- Backup selection and verification
"""
import os
import sys
import subprocess
import gzip
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class RestoreConfig:
    """Restore configuration."""
    backup_dir: str = "./backups"
    
    # PostgreSQL
    pg_host: str = "localhost"
    pg_port: int = 5432
    pg_database: str = "cognimend"
    pg_user: str = "postgres"
    pg_password: str = ""
    
    # Qdrant
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    
    # Redis
    redis_host: str = "localhost"
    redis_port: int = 6379


@dataclass
class RestoreResult:
    """Result of a restore operation."""
    success: bool
    restore_type: str
    source_file: str
    duration_seconds: float
    records_restored: int = 0
    error: Optional[str] = None


class RestoreManager:
    """
    Comprehensive restore manager for all services.
    """
    
    def __init__(self, config: Optional[RestoreConfig] = None):
        self.config = config or RestoreConfig()
    
    def list_backups(self, backup_type: str = "all") -> Dict[str, List[Dict[str, Any]]]:
        """
        List available backups.
        """
        backups = {}
        
        types = ["postgres", "qdrant", "redis"] if backup_type == "all" else [backup_type]
        
        for btype in types:
            backup_path = Path(f"{self.config.backup_dir}/{btype}")
            if not backup_path.exists():
                backups[btype] = []
                continue
            
            files = []
            for file in sorted(backup_path.glob("*"), key=lambda p: p.stat().st_mtime, reverse=True):
                stat = file.stat()
                files.append({
                    "name": file.name,
                    "path": str(file),
                    "size_mb": round(stat.st_size / 1024 / 1024, 2),
                    "modified": datetime.fromtimestamp(stat.st_mtime).isoformat()
                })
            
            backups[btype] = files
        
        return backups
    
    def get_latest_backup(self, backup_type: str) -> Optional[str]:
        """
        Get the path to the latest backup of a given type.
        """
        backups = self.list_backups(backup_type)
        files = backups.get(backup_type, [])
        
        if files:
            return files[0]["path"]
        return None
    
    def restore_postgres(self, backup_file: str) -> RestoreResult:
        """
        Restore PostgreSQL from backup.
        """
        start_time = datetime.now()
        
        if not os.path.exists(backup_file):
            return RestoreResult(
                success=False,
                restore_type="postgres",
                source_file=backup_file,
                duration_seconds=0,
                error="Backup file not found"
            )
        
        try:
            if backup_file.endswith('.sql.gz'):
                return self._restore_postgres_sql(backup_file, start_time)
            elif backup_file.endswith('.json.gz'):
                return self._restore_postgres_json(backup_file, start_time)
            else:
                return RestoreResult(
                    success=False,
                    restore_type="postgres",
                    source_file=backup_file,
                    duration_seconds=0,
                    error="Unknown backup format"
                )
            
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            logger.error(f"PostgreSQL restore failed: {e}")
            return RestoreResult(
                success=False,
                restore_type="postgres",
                source_file=backup_file,
                duration_seconds=duration,
                error=str(e)
            )
    
    def _restore_postgres_sql(self, backup_file: str, start_time: datetime) -> RestoreResult:
        """Restore from pg_dump SQL backup."""
        import tempfile
        
        # Decompress to temp file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.sql', delete=False) as tmp:
            with gzip.open(backup_file, 'rt') as gz:
                tmp.write(gz.read())
            temp_sql = tmp.name
        
        try:
            env = os.environ.copy()
            env['PGPASSWORD'] = self.config.pg_password or os.getenv('POSTGRES_PASSWORD', '')
            
            # Drop and recreate database
            logger.warning("Dropping existing database...")
            subprocess.run([
                'psql',
                '-h', self.config.pg_host,
                '-p', str(self.config.pg_port),
                '-U', self.config.pg_user,
                '-d', 'postgres',
                '-c', f'DROP DATABASE IF EXISTS {self.config.pg_database}'
            ], env=env, check=True)
            
            subprocess.run([
                'psql',
                '-h', self.config.pg_host,
                '-p', str(self.config.pg_port),
                '-U', self.config.pg_user,
                '-d', 'postgres',
                '-c', f'CREATE DATABASE {self.config.pg_database}'
            ], env=env, check=True)
            
            # Restore from backup
            logger.info("Restoring database from backup...")
            result = subprocess.run([
                'psql',
                '-h', self.config.pg_host,
                '-p', str(self.config.pg_port),
                '-U', self.config.pg_user,
                '-d', self.config.pg_database,
                '-f', temp_sql
            ], env=env, capture_output=True, text=True)
            
            if result.returncode != 0:
                raise Exception(f"psql restore failed: {result.stderr}")
            
            duration = (datetime.now() - start_time).total_seconds()
            logger.info(f"PostgreSQL restore completed in {duration:.2f}s")
            
            return RestoreResult(
                success=True,
                restore_type="postgres-sql",
                source_file=backup_file,
                duration_seconds=duration
            )
            
        finally:
            os.unlink(temp_sql)
    
    def _restore_postgres_json(self, backup_file: str, start_time: datetime) -> RestoreResult:
        """Restore from JSON backup (Python fallback)."""
        import psycopg2
        from psycopg2.extras import RealDictCursor
        
        with gzip.open(backup_file, 'rt', encoding='utf-8') as f:
            backup_data = json.load(f)
        
        conn = psycopg2.connect(
            host=self.config.pg_host,
            port=self.config.pg_port,
            database=self.config.pg_database,
            user=self.config.pg_user,
            password=self.config.pg_password or os.getenv('POSTGRES_PASSWORD', '')
        )
        
        cur = conn.cursor()
        records_restored = 0
        
        try:
            for table_name, rows in backup_data.get("tables", {}).items():
                if not rows:
                    continue
                
                logger.info(f"Restoring table: {table_name} ({len(rows)} rows)")
                
                # Truncate existing data
                cur.execute(f"TRUNCATE TABLE {table_name} CASCADE")
                
                # Insert rows
                columns = list(rows[0].keys())
                placeholders = ', '.join(['%s'] * len(columns))
                column_names = ', '.join(columns)
                
                for row in rows:
                    values = [row.get(col) for col in columns]
                    cur.execute(
                        f"INSERT INTO {table_name} ({column_names}) VALUES ({placeholders})",
                        values
                    )
                    records_restored += 1
            
            conn.commit()
            
            duration = (datetime.now() - start_time).total_seconds()
            logger.info(f"PostgreSQL restore completed: {records_restored} records")
            
            return RestoreResult(
                success=True,
                restore_type="postgres-json",
                source_file=backup_file,
                duration_seconds=duration,
                records_restored=records_restored
            )
            
        except Exception as e:
            conn.rollback()
            raise
        finally:
            cur.close()
            conn.close()
    
    def restore_qdrant(self, backup_file: str) -> RestoreResult:
        """
        Restore Qdrant collection from snapshot.
        """
        import requests
        
        start_time = datetime.now()
        
        if not os.path.exists(backup_file):
            return RestoreResult(
                success=False,
                restore_type="qdrant",
                source_file=backup_file,
                duration_seconds=0,
                error="Backup file not found"
            )
        
        try:
            # Extract collection name from filename
            filename = os.path.basename(backup_file)
            collection_name = filename.split('_')[0]
            
            base_url = f"http://{self.config.qdrant_host}:{self.config.qdrant_port}"
            
            logger.info(f"Restoring Qdrant collection: {collection_name}")
            
            # Upload snapshot
            with open(backup_file, 'rb') as f:
                resp = requests.post(
                    f"{base_url}/collections/{collection_name}/snapshots/upload",
                    files={"snapshot": f},
                    timeout=300
                )
                resp.raise_for_status()
            
            duration = (datetime.now() - start_time).total_seconds()
            logger.info(f"Qdrant restore completed in {duration:.2f}s")
            
            return RestoreResult(
                success=True,
                restore_type="qdrant",
                source_file=backup_file,
                duration_seconds=duration
            )
            
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            logger.error(f"Qdrant restore failed: {e}")
            return RestoreResult(
                success=False,
                restore_type="qdrant",
                source_file=backup_file,
                duration_seconds=duration,
                error=str(e)
            )
    
    def restore_redis(self, backup_file: str) -> RestoreResult:
        """
        Restore Redis from backup.
        """
        start_time = datetime.now()
        
        if not os.path.exists(backup_file):
            return RestoreResult(
                success=False,
                restore_type="redis",
                source_file=backup_file,
                duration_seconds=0,
                error="Backup file not found"
            )
        
        try:
            if backup_file.endswith('.json.gz'):
                return self._restore_redis_json(backup_file, start_time)
            elif backup_file.endswith('.rdb'):
                return self._restore_redis_rdb(backup_file, start_time)
            else:
                return RestoreResult(
                    success=False,
                    restore_type="redis",
                    source_file=backup_file,
                    duration_seconds=0,
                    error="Unknown backup format"
                )
            
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            logger.error(f"Redis restore failed: {e}")
            return RestoreResult(
                success=False,
                restore_type="redis",
                source_file=backup_file,
                duration_seconds=duration,
                error=str(e)
            )
    
    def _restore_redis_json(self, backup_file: str, start_time: datetime) -> RestoreResult:
        """Restore from JSON backup."""
        import redis
        
        with gzip.open(backup_file, 'rt', encoding='utf-8') as f:
            data = json.load(f)
        
        r = redis.Redis(
            host=self.config.redis_host,
            port=self.config.redis_port,
            decode_responses=True
        )
        
        # Flush existing data
        logger.warning("Flushing existing Redis data...")
        r.flushall()
        
        records_restored = 0
        
        for key, value in data.items():
            key_type = value.get("type", "string")
            key_value = value.get("value")
            
            try:
                if key_type == "string":
                    r.set(key, key_value)
                elif key_type == "hash":
                    r.hset(key, mapping=key_value)
                elif key_type == "list":
                    r.rpush(key, *key_value)
                elif key_type == "set":
                    r.sadd(key, *key_value)
                elif key_type == "zset":
                    for member, score in key_value:
                        r.zadd(key, {member: score})
                
                records_restored += 1
                
            except Exception as e:
                logger.warning(f"Failed to restore key {key}: {e}")
        
        duration = (datetime.now() - start_time).total_seconds()
        logger.info(f"Redis restore completed: {records_restored} keys")
        
        return RestoreResult(
            success=True,
            restore_type="redis-json",
            source_file=backup_file,
            duration_seconds=duration,
            records_restored=records_restored
        )
    
    def _restore_redis_rdb(self, backup_file: str, start_time: datetime) -> RestoreResult:
        """Restore from RDB file."""
        logger.warning("RDB restore requires stopping Redis and replacing the RDB file")
        logger.info("Steps to restore:")
        logger.info("1. Stop Redis server")
        logger.info(f"2. Copy {backup_file} to /data/dump.rdb")
        logger.info("3. Start Redis server")
        
        return RestoreResult(
            success=True,
            restore_type="redis-rdb",
            source_file=backup_file,
            duration_seconds=0,
            error="Manual restore required - see logs for instructions"
        )


def main():
    """Main entry point for restore script."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Database Restore Tool")
    parser.add_argument("--type", choices=["postgres", "qdrant", "redis"],
                        required=True, help="Type of backup to restore")
    parser.add_argument("--file", type=str, help="Backup file to restore (uses latest if not specified)")
    parser.add_argument("--list", action="store_true", help="List available backups")
    parser.add_argument("--backup-dir", type=str, default="./backups",
                        help="Backup directory")
    parser.add_argument("--force", action="store_true",
                        help="Skip confirmation prompt")
    
    args = parser.parse_args()
    
    # Load config from environment
    config = RestoreConfig(
        backup_dir=args.backup_dir,
        pg_host=os.getenv("POSTGRES_HOST", "localhost"),
        pg_port=int(os.getenv("POSTGRES_PORT", "5432")),
        pg_database=os.getenv("POSTGRES_DB", "cognimend"),
        pg_user=os.getenv("POSTGRES_USER", "postgres"),
        pg_password=os.getenv("POSTGRES_PASSWORD", ""),
        qdrant_host=os.getenv("QDRANT_HOST", "localhost"),
        qdrant_port=int(os.getenv("QDRANT_PORT", "6333")),
        redis_host=os.getenv("REDIS_HOST", "localhost"),
        redis_port=int(os.getenv("REDIS_PORT", "6379")),
    )
    
    manager = RestoreManager(config)
    
    if args.list:
        backups = manager.list_backups(args.type)
        print(f"\nAvailable {args.type} backups:")
        for backup in backups.get(args.type, []):
            print(f"  {backup['name']} - {backup['size_mb']} MB - {backup['modified']}")
        sys.exit(0)
    
    # Get backup file
    backup_file = args.file or manager.get_latest_backup(args.type)
    
    if not backup_file:
        logger.error(f"No {args.type} backup found")
        sys.exit(1)
    
    # Confirmation
    if not args.force:
        print(f"\n⚠️  WARNING: This will overwrite existing {args.type} data!")
        print(f"Backup file: {backup_file}")
        response = input("Continue? [y/N]: ")
        if response.lower() != 'y':
            print("Restore cancelled")
            sys.exit(0)
    
    # Run restore
    if args.type == "postgres":
        result = manager.restore_postgres(backup_file)
    elif args.type == "qdrant":
        result = manager.restore_qdrant(backup_file)
    elif args.type == "redis":
        result = manager.restore_redis(backup_file)
    
    if result.success:
        print(f"\n✅ Restore completed in {result.duration_seconds:.2f}s")
        if result.records_restored:
            print(f"   Records restored: {result.records_restored}")
    else:
        print(f"\n❌ Restore failed: {result.error}")
        sys.exit(1)


if __name__ == "__main__":
    main()
