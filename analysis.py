import csv
import os
import time

CLIENT_LOG = "clientPerformanceLog.csv"
SERVER_LOG = "serverPerformanceLog.csv"

def logMetrics(operation, fileName, sizeBytes, duration, logFile=CLIENT_LOG):
    # Universal logging function for both client and server operations."""
    dataRate = (sizeBytes / (1024 * 1024)) / duration if duration > 0 else 0
    fileSize = round(sizeBytes / (1024 * 1024), 4)
    
    fileExists = os.path.exists(logFile)
    
    with open(logFile, mode='a', newline='') as f:
        writer = csv.writer(f)
        if not fileExists:
            writer.writerow(["Timestamp", "Operation", "FileName", "FileSizeMB", "Duration_s", "DataRateMBs"])
        currentTimestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        
        writer.writerow([
            currentTimestamp, operation, fileName, fileSize,
            round(duration, 4), round(dataRate, 2)
        ])

def printLogTable(title, logFile):
    # Helper function to print a clean tabular summary for a log file."""
    if not os.path.exists(logFile):
        print(f"\n[{title}] No performance logs found at '{logFile}'.")
        return

    print(f"\n{'='*12} {title.upper()} PERFORMANCE LOG {'='*12}")
    # Print formatted table header
    print(f"{'Timestamp':<20} | {'Operation':<10} | {'FileName':<25} | {'Size (MB)':<10} | {'Duration (s)':<12} | {'Speed (MB/s)':<12}")
    print("-" * 101)

    with open(logFile, mode='r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            timestamp = row.get('Timestamp', '')
            op = row.get('Operation', '')
            fname = row.get('FileName', '')
            size = row.get('FileSizeMB', '')
            dur = row.get('Duration_s', '')
            speed = row.get('DataRateMBs', '') # Fixed key to match CSV header
            
            # Print formatted table row
            print(f"{timestamp:<20} | {op:<10} | {fname:<25} | {size:<10} | {dur:<12} | {speed:<12}")
    print("=" * 101)

def generateAnalysisSummary():
    # Reads and prints structured reports for both client and server logs."""
    print("\n========== FINAL PERFORMANCE ANALYSIS DASHBOARD ==========")
    printLogTable("Client Side", CLIENT_LOG)
    printLogTable("Server Side", SERVER_LOG)
    print("=========================================================")

if __name__ == "__main__":
    generateAnalysisSummary()