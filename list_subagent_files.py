import os

def list_files(startpath):
    print("--- Listing files in", startpath)
    for root, dirs, files in os.walk(startpath):
        level = root.replace(startpath, '').count(os.sep)
        indent = ' ' * 4 * (level)
        print(f"{indent}{os.path.basename(root)}/")
        subindent = ' ' * 4 * (level + 1)
        for f in files:
            print(f"{subindent}{f}")

if __name__ == "__main__":
    list_files(r"C:\Users\Ghost\.gemini\antigravity\brain\e62766b1-5a03-4aa4-a290-20115e1a1782")
