# PktMask User Guide

## I. Directory Processing

### 1. Directory Structure Requirements

* Select a target directory as the root.
* The software processes only direct subdirectories of this root directory.
* Deeper nested subdirectories are not processed.

### 2. Processing Example

TargetDirectory
|-- SubDir1 (processed)
|   |-- file1.pcap
|   |-- file2.pcap
|-- SubDir2 (processed)
|   |-- file3.pcap
|   |-- file4.pcap
|-- SubDir3 (processed)
    |-- file5.pcap
    |-- NestedSubDir (not processed)
        |-- file6.pcap

### 3. Generated Reports

* Each processed subdirectory generates two report files:

  * `replacement.log` (JSON format, detailed logs, and IP mappings).
  * `replacement.html` (visual statistical report).

## II. File Processing

### 1. Supported File Types

* `.pcap` and `.pcapng` files.
* Other file types are automatically ignored.

### 2. File Processing Rules

* Only original files without the `Replaced` suffix are processed.
* Processed files create new files with the `Replaced` suffix; original files remain unchanged.
* Existing `Replaced` files are overwritten by new processing results.

### 3. File Processing Example


Before Processing:
Subdirectory
|-- a.pcap
|-- b.pcap
|-- a-Replaced.pcap

After Processing:
Subdirectory
|-- a.pcap
|-- b.pcap
|-- a-Replaced.pcap (updated)
|-- b-Replaced.pcap (new)
|-- replacement.log
|-- replacement.html

## III. IP Address Replacement Logic

### 1. Replacement Principles

* Preserve original IP address structure and numeric features.
* Apply hierarchical, localized random replacements.
* Uniform replacements for frequently occurring prefixes.

### 2. IPv4 Address Processing

* The first three segments are replaced based on frequency (uniform or random).
* The fourth segment always remains unchanged.

### 3. IPv6 Address Processing

* The first seven segments are replaced based on frequency (uniform or random).
* The eighth segment always remains unchanged.

### 4. Special Address Handling

* Private addresses are randomly replaced while maintaining their type characteristics.
* Loopback and multicast addresses remain unchanged.

### 5. Cross-file Consistency

* Identical IP addresses within the same subdirectory are consistently replaced across files.
* IP mappings are independent between different subdirectories.

## IV. Result Statistics

* Total directories, processed directories, skipped directories.
* Total files, processed files, skipped files, failed files.
* Total unique IP addresses.

## V. Usage Recommendations

### 1. Directory Organization

* Group files needing uniform processing into the same subdirectory.
* Avoid deep directory structures.

### 2. File Preparation

* Use only `.pcap` or `.pcapng` files.
* Backup original files before processing.

### 3. During Execution

* The program automatically skips invalid files.
* Real-time monitoring through the interface to track progress.

### 4. Reviewing Results

* Use `replacement.html` for visual statistics.
* Check `replacement.log` for detailed IP mappings.

### 5. Cautions

* Do not modify files during processing.
* Ensure sufficient disk space is available.
* Initially test processing with a limited number of files.