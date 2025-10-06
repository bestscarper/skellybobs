
Write python code with a CLI for developers to use to generate initial code for hexagonal architecture for Java apps.
Read a template file "template.yaml" which represents the filesystem structure.
The template file represents part of a filesystem.
The resulting filesystem should be generated in a local subdirectory named "habuild".
Mustache-style placeholders are used to replace filenames, directory names, or in content blocks.
Replace placeholders using python CLI arguments.
Allow arguments "-p <placeholder> = <value>" to set the placeholders.
If a placeholder is defined multiple times in the context of a directory, repeat processing of that directory for each value.
Write the Python as a library so it can be reused.
Write a wrapper Python script to use the library for basic CLI use.
The YAML structure is recursive the field "content" represents either a file or a directory.
For a directory (type: directory), "content" is an array of elements in the named directory.
For a file (type: file) the content is a literal block of code which may have placeholders.
A directory name can have subdirectories (example: "api/src/main/java"), and we should create all intermediate directories.
If there is no "content" field for a block, then it means an empty file, or an empty directory.

Example of CLI command:
python3 skellybobs.py -p service=happiness -p group=peanuts -p adapter=http -p adapter=kafka


