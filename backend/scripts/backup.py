#!/usr/bin/env python3
"""
Database Backup Script

Provides:
- PostgreSQL backup with pg_dump
- Qdrant snapshot creation
- Redis backup (if AOF/RDB enabled)
- Backup verification
- S3 upload (optional)
- Retention policy enforcement
"""
import os
import sys
import subprocess
import gzip
import shutil
import logging
import hashlib
import json
from datetime import datetime, timedelta
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
class BackupConfig:
    """Backup configuration."""
    # Directories
    backup_dir: str = "./backups"
    temp_dir: str = "./backups/temp"
    
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
    
    # Retention
    keep_daily: int = 7
    keep_weekly: int = 4
    keep_monthly: int = 3
    
    # S3 (optional)
    s3_bucket: Optional[str] = None
    s3_prefix: str = "backups"
    aws_region: str = "us-east-1"


@dataclass
class BackupResult:
    """Result of a backup operation."""
    success: bool
    backup_type: str
    file_path: Optional[str]
    size_bytes: int
    duration_seconds: float
    checksum: Optional[str]
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "backup_type": self.backup_type,
            "file_path": self.file_path,
            "size_bytes": self.size_bytes,
            "size_mb": round(self.size_bytes / 1024 / 1024, 2),
            "duration_seconds": round(self.duration_seconds, 2),
            "checksum": self.checksum,
            "error": self.error
        }


class BackupManager:
    """
    Comprehensive backup manager for all services.
    """
    
    def __init__(self, config: Optional[BackupConfig] = None):
        self.config = config or BackupConfig()
        self._ensure_directories()
    
    def _ensure_directories(self) -> None:
        """Create backup directories if they don't exist."""
        Path(self.config.backup_dir).mkdir(parents=True, exist_ok=True)
        Path(self.config.temp_dir).mkdir(parents=True, exist_ok=True)
        Path(f"{self.config.backup_dir}/postgres").mkdir(exist_ok=True)
        Path(f"{self.config.backup_dir}/qdrant").mkdir(exist_ok=True)
        Path(f"{self.config.backup_dir}/redis").mkdir(exist_ok=True)
    
    def _get_timestamp(self) -> str:
        """Get timestamp for backup filename."""
        return datetime.now().strftime("%Y%m%d_%H%M%S")
    
    def _calculate_checksum(self, file_path: str) -> str:
        """Calculate SHA256 checksum of a file."""
        sha256 = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                sha256.update(chunk)
        return sha256.hexdigest()
    
    def backup_postgres(self) -> BackupResult:
        """
        Backup PostgreSQL database using pg_dump.
        """
        timestamp = self._get_timestamp()
        backup_file = f"{self.config.backup_dir}/postgres/pg_{timestamp}.sql.gz"
        temp_file = f"{self.config.temp_dir}/pg_{timestamp}.sql"
        
        start_time = datetime.now()
        
        try:
            # Set environment for pg_dump
            env = os.environ.copy()
            env['PGPASSWORD'] = self.config.pg_password or os.getenv('POSTGRES_PASSWORD', '')
            
            # Run pg_dump
            cmd = [
                'pg_dump',
                '-h', self.config.pg_host,
                '-p', str(self.config.pg_port),
                '-U', self.config.pg_user,
                '-d', self.config.pg_database,
                '-F', 'p',  # Plain text format
                '-f', temp_file
            ]
            
            logger.info(f"Running pg_dump for database {self.config.pg_database}")
            result = subprocess.run(cmd, env=env, capture_output=True, text=True)
            
            if result.returncode != 0:
                raise Exception(f"pg_dump failed: {result.stderr}")
            
            # Compress the backup
            logger.info("Compressing backup...")
            with open(temp_file, 'rb') as f_in:
                with gzip.open(backup_file, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
            
            # Remove temp file
            os.remove(temp_file)
            
            # Get file size and checksum
            size = os.path.getsize(backup_file)
            checksum = self._calculate_checksum(backup_file)
            
            duration = (datetime.now() - start_time).total_seconds()
            
            logger.info(f"PostgreSQL backup completed: {backup_file} ({size / 1024 / 1024:.2f} MB)")
            
            return BackupResult(
                success=True,
                backup_type="postgres",
                file_path=backup_file,
                size_bytes=size,
                duration_seconds=duration,
                checksum=checksum
            )
            
        except FileNotFoundError:
            # pg_dump not found, try Python fallback
            return self._backup_postgres_python(timestamp, start_time)
            
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            logger.error(f"PostgreSQL backup failed: {e}")
            return BackupResult(
                success=False,
                backup_type="postgres",
                file_path=None,
                size_bytes=0,
                duration_seconds=duration,
                checksum=None,
                error=str(e)
            )
    
    def _backup_postgres_python(self, timestamp: str, start_time: datetime) -> BackupResult:
        """Fallback PostgreSQL backup using Python."""
        import psycopg2
        from psycopg2.extras import RealDictCursor
        
        backup_file = f"{self.config.backup_dir}/postgres/pg_{timestamp}.json.gz"
        
        try:
            conn = psycopg2.connect(
                host=self.config.pg_host,
                port=self.config.pg_port,
                database=self.config.pg_database,
                user=self.config.pg_user,
                password=self.config.pg_password or os.getenv('POSTGRES_PASSWORD', '')
            )
            
            cur = conn.cursor(cursor_factory=RealDictCursor)
            
            # Get all tables
            cur.execute("""
                SELECT table_name FROM information_schema.tables 
                WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
            """)
            tables = [row['table_name'] for row in cur.fetchall()]
            
            backup_data = {
                "metadata": {
                    "timestamp": datetime.now().isoformat(),
                    "database": self.config.pg_database,
                    "tables": tables
                },
                "tables": {}
            }
            
            for table in tables:
                logger.info(f"Backing up table: {table}")
                cur.execute(f"SELECT * FROM {table}")
                rows = cur.fetchall()
                backup_data["tables"][table] = [dict(row) for row in rows]
            
            cur.close()
            conn.close()
            
            # Write compressed JSON
            with gzip.open(backup_file, 'wt', encoding='utf-8') as f:
                json.dump(backup_data, f, default=str, indent=2)
            
            size = os.path.getsize(backup_file)
            checksum = self._calculate_checksum(backup_file)
            duration = (datetime.now() - start_time).total_seconds()
            
            logger.info(f"PostgreSQL backup (Python) completed: {backup_file}")
            
            return BackupResult(
                success=True,
                backup_type="postgres-python",
                file_path=backup_file,
                size_bytes=size,
                duration_seconds=duration,
                checksum=checksum
            )
            
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            logger.error(f"PostgreSQL Python backup failed: {e}")
            return BackupResult(
                success=False,
                backup_type="postgres-python",
                file_path=None,
                size_bytes=0,
                duration_seconds=duration,
                checksum=None,
                error=str(e)
            )
    
    def backup_qdrant(self) -> BackupResult:
        """
        Backup Qdrant by creating a snapshot.
        """
        import requests
        
        timestamp = self._get_timestamp()
        start_time = datetime.now()
        
        try:
            base_url = f"http://{self.config.qdrant_host}:{self.config.qdrant_port}"
            
            # Get all collections
            resp = requests.get(f"{base_url}/collections", timeout=10)
            resp.raise_for_status()
            collections = resp.json()["result"]["collections"]
            
            backup_files = []
            total_size = 0
            
            for coll in collections:
                coll_name = coll["name"]
                logger.info(f"Creating snapshot for collection: {coll_name}")
                
                # Create snapshot
                resp = requests.post(
                    f"{base_url}/collections/{coll_name}/snapshots",
                    timeout=300
                )
                resp.raise_for_status()
                snapshot_name = resp.json()["result"]["name"]
                
                # Download snapshot
                backup_file = f"{self.config.backup_dir}/qdrant/{coll_name}_{timestamp}.snapshot"
                resp = requests.get(
                    f"{base_url}/collections/{coll_name}/snapshots/{snapshot_name}",
                    stream=True,
                    timeout=300
                )
                resp.raise_for_status()
                
                with open(backup_file, 'wb') as f:
                    for chunk in resp.iter_content(chunk_size=8192):
                        f.write(chunk)
                
                backup_files.append(backup_file)
                total_size += os.path.getsize(backup_file)
                
                # Delete snapshot from server
                requests.delete(
                    f"{base_url}/collections/{coll_name}/snapshots/{snapshot_name}",
                    timeout=30
                )
            
            duration = (datetime.now() - start_time).total_seconds()
            
            logger.info(f"Qdrant backup completed: {len(backup_files)} collections")
            
            return BackupResult(
                success=True,
                backup_type="qdrant",
                file_path=",".join(backup_files) if backup_files else None,
                size_bytes=total_size,
                duration_seconds=duration,
                checksum=None
            )
            
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            logger.error(f"Qdrant backup failed: {e}")
            return BackupResult(
                success=False,
                backup_type="qdrant",
                file_path=None,
                size_bytes=0,
                duration_seconds=duration,
                checksum=None,
                error=str(e)
            )
    
    def backup_redis(self) -> BackupResult:
        """
        Backup Redis using BGSAVE.
        """
        import redis
        
        timestamp = self._get_timestamp()
        backup_file = f"{self.config.backup_dir}/redis/redis_{timestamp}.rdb"
        start_time = datetime.now()
        
        try:
            r = redis.Redis(
                host=self.config.redis_host,
                port=self.config.redis_port,
                decode_responses=True
            )
            
            # Trigger background save
            logger.info("Triggering Redis BGSAVE...")
            r.bgsave()
            
            # Wait for save to complete
            while True:
                info = r.info("persistence")
                if info.get("rdb_bgsave_in_progress", 0) == 0:
                    break
                logger.debug("Waiting for BGSAVE to complete...")
                import time
                time.sleep(0.5)
            
            # Get the RDB file location
            rdb_path = info.get("rdb_last_save_file", "/data/dump.rdb")
            
            # Copy RDB file (if accessible)
            if os.path.exists(rdb_path):
                shutil.copy2(rdb_path, backup_file)
                size = os.path.getsize(backup_file)
                checksum = self._calculate_checksum(backup_file)
            else:
                # If RDB file not accessible, dump all keys (slow for large DBs)
                logger.warning("RDB file not accessible, using KEY dump fallback")
                return self._backup_redis_dump(r, timestamp, start_time)
            
            duration = (datetime.now() - start_time).total_seconds()
            
            logger.info(f"Redis backup completed: {backup_file}")
            
            return BackupResult(
                success=True,
                backup_type="redis",
                file_path=backup_file,
                size_bytes=size,
                duration_seconds=duration,
                checksum=checksum
            )
            
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            logger.error(f"Redis backup failed: {e}")
            return BackupResult(
                success=False,
                backup_type="redis",
                file_path=None,
                size_bytes=0,
                duration_seconds=duration,
                checksum=None,
                error=str(e)
            )
    
    def _backup_redis_dump(self, r, timestamp: str, start_time: datetime) -> BackupResult:
        """Fallback Redis backup using DUMP command."""
        backup_file = f"{self.config.backup_dir}/redis/redis_{timestamp}.json.gz"
        
        try:
            keys = r.keys("*")
            data = {}
            
            for key in keys:
                try:
                    key_type = r.type(key)
                    if key_type == "string":
                        data[key] = {"type": "string", "value": r.get(key)}
                    elif key_type == "hash":
                        data[key] = {"type": "hash", "value": dict(r.hgetall(key))}
                    elif key_type == "list":
                        data[key] = {"type": "list", "value": r.lrange(key, 0, -1)}
                    elif key_type == "set":
                        data[key] = {"type": "set", "value": list(r.smembers(key))}
                    elif key_type == "zset":
                        data[key] = {"type": "zset", "value": r.zrange(key, 0, -1, withscores=True)}
                except Exception as e:
                    logger.warning(f"Failed to backup key {key}: {e}")
            
            with gzip.open(backup_file, 'wt', encoding='utf-8') as f:
                json.dump(data, f)
            
            size = os.path.getsize(backup_file)
            checksum = self._calculate_checksum(backup_file)
            duration = (datetime.now() - start_time).total_seconds()
            
            return BackupResult(
                success=True,
                backup_type="redis-dump",
                file_path=backup_file,
                size_bytes=size,
                duration_seconds=duration,
                checksum=checksum
            )
            
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            return BackupResult(
                success=False,
                backup_type="redis-dump",
                file_path=None,
                size_bytes=0,
                duration_seconds=duration,
                checksum=None,
                error=str(e)
            )
    
    def backup_all(self) -> Dict[str, BackupResult]:
        """
        Run all backups.
        """
        logger.info("=" * 50)
        logger.info("Starting full backup")
        logger.info("=" * 50)
        
        results = {}
        
        # PostgreSQL
        logger.info("\n--- PostgreSQL Backup ---")
        results["postgres"] = self.backup_postgres()
        
        # Qdrant
        logger.info("\n--- Qdrant Backup ---")
        results["qdrant"] = self.backup_qdrant()
        
        # Redis
        logger.info("\n--- Redis Backup ---")
        results["redis"] = self.backup_redis()
        
        # Summary
        logger.info("\n" + "=" * 50)
        logger.info("Backup Summary")
        logger.info("=" * 50)
        
        for name, result in results.items():
            status = "✅" if result.success else "❌"
            size = f"{result.size_bytes / 1024 / 1024:.2f} MB" if result.success else "N/A"
            logger.info(f"{status} {name}: {size} ({result.duration_seconds:.2f}s)")
            if result.error:
                logger.error(f"   Error: {result.error}")
        
        return results
    
    def cleanup_old_backups(self) -> Dict[str, int]:
        """
        Remove old backups based on retention policy.
        """
        logger.info("Cleaning up old backups...")
        
        removed = {"postgres": 0, "qdrant": 0, "redis": 0}
        now = datetime.now()
        
        for backup_type in ["postgres", "qdrant", "redis"]:
            backup_path = Path(f"{self.config.backup_dir}/{backup_type}")
            if not backup_path.exists():
                continue
            
            files = sorted(backup_path.glob("*"), key=lambda p: p.stat().st_mtime)
            
            for file in files:
                file_age = now - datetime.fromtimestamp(file.stat().st_mtime)
                
                # Keep recent daily backups
                if file_age < timedelta(days=self.config.keep_daily):
                    continue
                
                # Keep weekly backups
                if file_age < timedelta(weeks=self.config.keep_weekly):
                    # Keep only if it's from a Sunday (weekly backup)
                    file_date = datetime.fromtimestamp(file.stat().st_mtime)
                    if file_date.weekday() == 6:
                        continue
                
                # Keep monthly backups
                if file_age < timedelta(days=self.config.keep_monthly * 30):
                    # Keep only if it's from the 1st of the month
                    file_date = datetime.fromtimestamp(file.stat().st_mtime)
                    if file_date.day == 1:
                        continue
                
                # Remove old backup
                logger.info(f"Removing old backup: {file}")
                file.unlink()
                removed[backup_type] += 1
        
        return removed
    
    def verify_backup(self, backup_file: str) -> bool:
        """
        Verify a backup file integrity.
        """
        try:
            if not os.path.exists(backup_file):
                logger.error(f"Backup file not found: {backup_file}")
                return False
            
            # Check file size
            size = os.path.getsize(backup_file)
            if size == 0:
                logger.error("Backup file is empty")
                return False
            
            # Try to decompress if gzipped
            if backup_file.endswith('.gz'):
                with gzip.open(backup_file, 'rb') as f:
                    # Read first chunk to verify
                    chunk = f.read(1024)
                    if not chunk:
                        logger.error("Backup file appears corrupted")
                        return False
            
            logger.info(f"Backup verified: {backup_file}")
            return True
            
        except Exception as e:
            logger.error(f"Backup verification failed: {e}")
            return False


def main():
    """Main entry point for backup script."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Database Backup Tool")
    parser.add_argument("--type", choices=["all", "postgres", "qdrant", "redis"],
                        default="all", help="Type of backup to perform")
    parser.add_argument("--cleanup", action="store_true",
                        help="Clean up old backups after backup")
    parser.add_argument("--verify", type=str, help="Verify a backup file")
    parser.add_argument("--backup-dir", type=str, default="./backups",
                        help="Backup directory")
    
    args = parser.parse_args()
    
    # Load config from environment
    config = BackupConfig(
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
    
    manager = BackupManager(config)
    
    if args.verify:
        success = manager.verify_backup(args.verify)
        sys.exit(0 if success else 1)
    
    if args.type == "all":
        results = manager.backup_all()
    elif args.type == "postgres":
        results = {"postgres": manager.backup_postgres()}
    elif args.type == "qdrant":
        results = {"qdrant": manager.backup_qdrant()}
    elif args.type == "redis":
        results = {"redis": manager.backup_redis()}
    
    if args.cleanup:
        manager.cleanup_old_backups()
    
    # Exit with error if any backup failed
    if any(not r.success for r in results.values()):
        sys.exit(1)


if __name__ == "__main__":
    main()
