import sqlite3 from 'sqlite3';
import { resolve } from 'path';
import fs from 'fs';

// Extend sqlite3 with promise-based methods
interface Database {
  all<T = any>(sql: string, params?: any[]): Promise<T[]>;
  get<T = any>(sql: string, params?: any[]): Promise<T>;
  run(sql: string, params?: any[]): Promise<{ lastID: number; changes: number }>;
  exec(sql: string): Promise<void>;
}

let db: Database | null = null;

/**
 * Set up the database connection
 */
export function setupDatabase(): Database {
  if (db) return db;
  
  const dbPath = process.env.DB_PATH || resolve(__dirname, '../../../disclosures.db');
  
  // Check if the database file exists
  if (!fs.existsSync(dbPath)) {
    console.warn(`Database file not found at ${dbPath}. Creating a new database file.`);
  }
  
  // Create a new database connection
  const sqlite = new sqlite3.Database(dbPath, (err) => {
    if (err) {
      console.error('Error connecting to the database:', err.message);
      process.exit(1);
    }
    console.log(`Connected to SQLite database at ${dbPath}`);
  });
  
  // Wrap sqlite3 methods with promises
  db = {
    all: <T = any>(sql: string, params: any[] = []): Promise<T[]> => {
      return new Promise((resolve, reject) => {
        sqlite.all(sql, params, (err, rows) => {
          if (err) reject(err);
          else resolve(rows as T[]);
        });
      });
    },
    
    get: <T = any>(sql: string, params: any[] = []): Promise<T> => {
      return new Promise((resolve, reject) => {
        sqlite.get(sql, params, (err, row) => {
          if (err) reject(err);
          else resolve(row as T);
        });
      });
    },
    
    run: (sql: string, params: any[] = []): Promise<{ lastID: number; changes: number }> => {
      return new Promise((resolve, reject) => {
        sqlite.run(sql, params, function(err) {
          if (err) reject(err);
          else resolve({ lastID: this.lastID, changes: this.changes });
        });
      });
    },
    
    exec: (sql: string): Promise<void> => {
      return new Promise((resolve, reject) => {
        sqlite.exec(sql, (err) => {
          if (err) reject(err);
          else resolve();
        });
      });
    }
  };
  
  return db;
}

/**
 * Get the database connection
 */
export function getConnection(): Database {
  if (!db) {
    return setupDatabase();
  }
  return db;
} 