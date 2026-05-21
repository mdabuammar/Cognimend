/**
 * Performance Benchmarks
 * 
 * Vitest benchmarks for critical functions.
 * Run with: npm run test:bench
 */

import { bench, describe } from 'vitest';
import {
  escapeHtml,
  stripHtml,
  sanitizeInput,
  sanitizeQuery,
  sanitizeFilename,
  sanitizeForLogging,
} from '../lib/security/sanitize';

describe('Sanitization Performance', () => {
  const shortString = 'Hello <script>alert("xss")</script> World';
  const mediumString = shortString.repeat(100);
  const longString = shortString.repeat(1000);

  describe('escapeHtml', () => {
    bench('short string', () => {
      escapeHtml(shortString);
    });

    bench('medium string (4KB)', () => {
      escapeHtml(mediumString);
    });

    bench('long string (40KB)', () => {
      escapeHtml(longString);
    });
  });

  describe('stripHtml', () => {
    bench('short string', () => {
      stripHtml(shortString);
    });

    bench('medium string (4KB)', () => {
      stripHtml(mediumString);
    });

    bench('long string (40KB)', () => {
      stripHtml(longString);
    });
  });

  describe('sanitizeInput', () => {
    bench('short string', () => {
      sanitizeInput(shortString);
    });

    bench('medium string (4KB)', () => {
      sanitizeInput(mediumString);
    });

    bench('with options', () => {
      sanitizeInput(mediumString, { maxLength: 1000, allowNewlines: false });
    });
  });

  describe('sanitizeQuery', () => {
    const normalQuery = 'How many vacation days do employees get?';
    const suspiciousQuery = 'SELECT * FROM users; DROP TABLE users;';

    bench('normal query', () => {
      sanitizeQuery(normalQuery);
    });

    bench('suspicious query (with pattern detection)', () => {
      sanitizeQuery(suspiciousQuery);
    });

    bench('long query', () => {
      sanitizeQuery(normalQuery.repeat(50));
    });
  });

  describe('sanitizeFilename', () => {
    bench('normal filename', () => {
      sanitizeFilename('document.pdf');
    });

    bench('malicious filename', () => {
      sanitizeFilename('../../../etc/passwd');
    });

    bench('long filename', () => {
      sanitizeFilename('a'.repeat(500) + '.pdf');
    });
  });

  describe('sanitizeForLogging', () => {
    const smallObject = {
      username: 'john',
      password: 'secret',
      email: 'john@example.com',
    };

    const largeObject = Object.fromEntries(
      Array.from({ length: 100 }, (_, i) => [`field${i}`, `value${i}`])
    );

    bench('small object', () => {
      sanitizeForLogging(smallObject);
    });

    bench('large object (100 fields)', () => {
      sanitizeForLogging(largeObject);
    });
  });
});

describe('Cache Performance', () => {
  // Simple LRU cache mock for benchmarking
  class SimpleLRUCache<T> {
    private cache = new Map<string, T>();
    private maxSize: number;

    constructor(maxSize: number) {
      this.maxSize = maxSize;
    }

    get(key: string): T | undefined {
      const value = this.cache.get(key);
      if (value !== undefined) {
        // Move to end (most recently used)
        this.cache.delete(key);
        this.cache.set(key, value);
      }
      return value;
    }

    set(key: string, value: T): void {
      if (this.cache.has(key)) {
        this.cache.delete(key);
      } else if (this.cache.size >= this.maxSize) {
        // Remove oldest
        const oldestKey = this.cache.keys().next().value;
        if (oldestKey) this.cache.delete(oldestKey);
      }
      this.cache.set(key, value);
    }
  }

  describe('LRU Cache', () => {
    const cache = new SimpleLRUCache<string>(1000);

    // Pre-populate cache
    for (let i = 0; i < 500; i++) {
      cache.set(`key${i}`, `value${i}`);
    }

    bench('cache hit', () => {
      cache.get('key250');
    });

    bench('cache miss', () => {
      cache.get('nonexistent');
    });

    bench('cache set (existing)', () => {
      cache.set('key100', 'newvalue');
    });

    bench('cache set (new, no eviction)', () => {
      cache.set(`newkey${Math.random()}`, 'value');
    });
  });
});

describe('Serialization Performance', () => {
  const smallObject = { id: 1, name: 'Test', value: 123.45 };
  const mediumObject = {
    id: 1,
    name: 'Test User',
    email: 'test@example.com',
    profile: {
      bio: 'Lorem ipsum dolor sit amet',
      avatar: 'https://example.com/avatar.png',
      settings: { theme: 'dark', notifications: true },
    },
    permissions: ['read', 'write', 'delete'],
  };
  const largeObject = {
    ...mediumObject,
    items: Array.from({ length: 100 }, (_, i) => ({
      id: i,
      name: `Item ${i}`,
      value: Math.random(),
    })),
  };

  bench('JSON.stringify small object', () => {
    JSON.stringify(smallObject);
  });

  bench('JSON.stringify medium object', () => {
    JSON.stringify(mediumObject);
  });

  bench('JSON.stringify large object', () => {
    JSON.stringify(largeObject);
  });

  const smallJson = JSON.stringify(smallObject);
  const mediumJson = JSON.stringify(mediumObject);
  const largeJson = JSON.stringify(largeObject);

  bench('JSON.parse small JSON', () => {
    JSON.parse(smallJson);
  });

  bench('JSON.parse medium JSON', () => {
    JSON.parse(mediumJson);
  });

  bench('JSON.parse large JSON', () => {
    JSON.parse(largeJson);
  });
});

describe('String Operations Performance', () => {
  const shortText = 'Hello World';
  const mediumText = 'Lorem ipsum dolor sit amet, consectetur adipiscing elit. '.repeat(100);
  const longText = mediumText.repeat(10);

  describe('String Search', () => {
    bench('indexOf short', () => {
      shortText.indexOf('World');
    });

    bench('indexOf medium', () => {
      mediumText.indexOf('consectetur');
    });

    bench('includes medium', () => {
      mediumText.includes('consectetur');
    });

    bench('regex search medium', () => {
      /consectetur/i.test(mediumText);
    });

    bench('indexOf long (at end)', () => {
      longText.indexOf('elit.');
    });
  });

  describe('String Replace', () => {
    bench('replace single', () => {
      mediumText.replace('ipsum', 'IPSUM');
    });

    bench('replace all', () => {
      mediumText.replace(/ipsum/g, 'IPSUM');
    });

    bench('replaceAll', () => {
      mediumText.replaceAll('ipsum', 'IPSUM');
    });
  });
});
