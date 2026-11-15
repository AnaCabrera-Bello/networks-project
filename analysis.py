import csv
import os
import time

STATS_LOG_FILE = "clientPerformanceLog.csv"

def logMetrics(operation, fileName, sizeBytes, duration):
    # logs performance metrics for project report using built-in csv module
    dataRate = (sizeBytes / (1024 * 1024)) / duration if duration > 0 else 0
    fileSize = round(sizeBytes / (1024 * 1024), 2)
    
    fileExists = os.path.exists(STATS_LOG_FILE)
    
    # save directly to csv
    with open(STATS_LOG_FILE, mode='a', newline='') as f:
        writer = csv.writer(f)
        if not fileExists:
            writer.writerow(["Timestamp", "Operation", "FileName", "FileSizeMB", "Duration_s", "DataRateMBs"])
        currentTimestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        
        # record execution metrics row
        writer.writerow([
            currentTimestamp, operation, fileName, fileSize,
            round(duration, 4), round(dataRate, 2)
        ])
        
def generate_analysis_summary():
    # reads and prints records for presentation and report analysis
    if not os.path.exists(STATS_LOG_FILE):
        print("[ANALYSIS] No performance logs recorded yet.")
        return

    print("\n========== PERFORMANCE ANALYSIS MODULE ==========")
    with open(STATS_LOG_FILE, mode='r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            print(f"[{row['Operation']}] {row['FileName']} ({row['FileSizeMB']} MB) - Time: {row['Duration_s']}s - Speed: {row['DataRate_MBs']} MB/s")
    print("=================================================")

if __name__ == "__main__":
    generate_analysis_summary()