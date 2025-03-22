#!/usr/bin/env python3
"""
Monitor Recategorization Progress

This script checks the current state of the database and shows the progress
of the recategorization process.
"""

import sqlite3
import argparse
import time
from datetime import datetime

def check_progress(db_path, interval=60):
    """
    Monitor the progress of recategorization.
    
    Args:
        db_path: Path to the SQLite database
        interval: Interval in seconds between checks
    """
    print(f"Monitoring recategorization progress of {db_path}")
    print(f"Press Ctrl+C to stop monitoring")
    print("-" * 60)
    
    initial_counts = None
    
    try:
        while True:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Get category counts
            cursor.execute("""
                SELECT category, COUNT(*) 
                FROM disclosures 
                GROUP BY category
                ORDER BY COUNT(*) DESC
            """)
            
            category_counts = {category: count for category, count in cursor.fetchall()}
            
            # Get total count
            cursor.execute("SELECT COUNT(*) FROM disclosures")
            total_count = cursor.fetchone()[0]
            
            # If this is the first check, store the initial counts
            if initial_counts is None:
                initial_counts = category_counts.copy()
            
            # Calculate changes
            changes = {
                cat: count - initial_counts.get(cat, 0) 
                for cat, count in category_counts.items()
            }
            
            # Display current status
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"\nStatus as of {now}:")
            print(f"Total entries: {total_count}")
            
            # Display category counts
            print("\nCategory distribution:")
            for category, count in category_counts.items():
                percentage = (count / total_count) * 100
                change = changes.get(category, 0)
                change_str = f" ({change:+d})" if change != 0 else ""
                print(f"  - {category}: {count:,} entries ({percentage:.1f}%){change_str}")
            
            # Check if Unknown category exists and show percentage
            unknown_count = category_counts.get("Unknown", 0)
            if unknown_count > 0:
                unknown_percentage = (unknown_count / total_count) * 100
                unknown_change = changes.get("Unknown", 0)
                print(f"\nRemaining Unknown: {unknown_count:,} entries ({unknown_percentage:.1f}%) ({unknown_change:+d})")
                print(f"Progress: {100 - unknown_percentage:.1f}% categorized")
            
            conn.close()
            
            # Sleep until next check
            print(f"\nNext update in {interval} seconds...")
            time.sleep(interval)
            
    except KeyboardInterrupt:
        print("\nMonitoring stopped.")
    except Exception as e:
        print(f"Error: {str(e)}")

def main():
    """Parse arguments and run the monitor."""
    parser = argparse.ArgumentParser(description="Monitor recategorization progress")
    parser.add_argument("--db-path", default="disclosures.db", help="Path to the SQLite database file")
    parser.add_argument("--interval", type=int, default=60, help="Interval in seconds between checks")
    
    args = parser.parse_args()
    
    check_progress(args.db_path, args.interval)

if __name__ == "__main__":
    main() 