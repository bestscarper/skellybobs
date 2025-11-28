import os
import re
import sys
from collections import defaultdict
from pathlib import Path

def remove_comments(text):
    """
    Removes C-style comments (// and /* */) from Java source code.
    This prevents finding class usages inside commented-out code.
    """
    def replacer(match):
        s = match.group(0)
        if s.startswith('/'):
            return " " # replace comment with space
        else:
            return s # return string literal

    # Regex to capture comments or string literals (to ignore comments inside strings)
    pattern = re.compile(
        r'//.*?$|/\*.*?\*/|\'(?:\\.|[^\\\'])*\'|"(?:\\.|[^\\"])*"',
        re.DOTALL | re.MULTILINE
    )
    return re.sub(pattern, replacer, text)

def get_class_name(file_path):
    """
    Extracts the simple class name from the filename.
    Example: /path/to/UserService.java -> UserService
    """
    return Path(file_path).stem

def is_test_file(file_path):
    """
    Determines if a file is a test class based on path conventions.
    """
    path_str = str(file_path).lower()
    # Standard Maven/Gradle convention
    if 'src/test/java' in path_str or 'src\\test\\java' in path_str:
        return True
    # Fallback: check if file ends with Test.java or Tests.java
    if path_str.endswith('test.java') or path_str.endswith('tests.java'):
        return True
    return False

def analyze_java_project(root_dir):
    print(f"Scanning directory: {root_dir} ...")

    prod_classes = {} # Map: ClassName -> FilePath
    all_files = []    # List of tuples: (FilePath, is_test_bool, content_no_comments)

    # 1. Index all files
    for root, dirs, files in os.walk(root_dir):
        for file in files:
            if file.endswith(".java"):
                full_path = Path(root) / file
                is_test = is_test_file(full_path)
                class_name = get_class_name(full_path)

                try:
                    with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                        clean_content = remove_comments(content)

                        all_files.append({
                            'path': full_path,
                            'is_test': is_test,
                            'content': clean_content,
                            'name': class_name
                        })

                        if not is_test:
                            # Handle duplicate class names (simple heuristic: warn user)
                            if class_name in prod_classes:
                                print(f"[WARN] Duplicate class name found: {class_name}. Analysis may be imprecise.")
                            prod_classes[class_name] = full_path
                except Exception as e:
                    print(f"[ERROR] Could not read file {full_path}: {e}")

    print(f"Found {len(prod_classes)} production classes.")
    print(f"Found {len(all_files)} total Java files.")
    print("-" * 50)

    # 2. Analyze usages
    # Map: ProdClassName -> {'prod_refs': int, 'test_refs': int, 'test_files': []}
    usage_stats = {
        name: {'prod_refs': 0, 'test_refs': 0, 'test_files': []}
        for name in prod_classes
    }

    for file_data in all_files:
        content = file_data['content']
        current_file_is_test = file_data['is_test']
        current_file_name = file_data['name']

        # Check for usage of every known production class
        for target_class, target_path in prod_classes.items():

            # Don't check if a class uses itself
            if target_class == current_file_name:
                continue

            # Heuristic: Regex word boundary search
            # We look for \bClassName\b. This avoids matching "User" inside "UserService".
            if re.search(r'\b' + re.escape(target_class) + r'\b', content):
                if current_file_is_test:
                    usage_stats[target_class]['test_refs'] += 1
                    usage_stats[target_class]['test_files'].append(file_data['name'])
                else:
                    usage_stats[target_class]['prod_refs'] += 1

    # 3. Filter Results
    results = []
    unused_classes = []

    for class_name, stats in usage_stats.items():
        if stats['prod_refs'] == 0:
            if stats['test_refs'] > 0:
                results.append((class_name, prod_classes[class_name], stats['test_files']))
            else:
                unused_classes.append(class_name)

    return results, unused_classes

def main():
    if len(sys.argv) < 2:
        print("Usage: python find_test_only_classes.py <path_to_java_project>")
        sys.exit(1)

    project_path = sys.argv[1]
    if not os.path.isdir(project_path):
        print("Error: The provided path is not a directory.")
        sys.exit(1)

    test_only, totally_unused = analyze_java_project(project_path)

    print(f"\nAnalysis Complete.")

    if test_only:
        print(f"\n[FOUND] {len(test_only)} classes used ONLY by tests:")
        print("=" * 60)
        # Sort by class name
        test_only.sort(key=lambda x: x[0])

        for cls, path, test_users in test_only:
            print(f"Class: {cls}")
            print(f"Path : {path}")
            # Show first 3 test clients to avoid clutter
            shown_tests = ", ".join(test_users[:3])
            remaining = len(test_users) - 3
            suffix = f" ... and {remaining} others" if remaining > 0 else ""
            print(f"Used by: {shown_tests}{suffix}")
            print("-" * 60)
    else:
        print("\nGood news! No classes found that are only used by tests.")

    if totally_unused:
        print(f"\n[INFO] Found {len(totally_unused)} classes with NO references found (Potential dead code or Entry points):")
        # Print first 10
        print(", ".join(totally_unused[:10]) + ("..." if len(totally_unused) > 10 else ""))

if __name__ == "__main__":
    main()