# Skellybobs

A simple code-generation (skeleton) system. Generate a customisable filestructure for a given template.

The templates are structured as YAML files.

See `template.yaml` as an example.

## Overview

### Code generation from templates

To generate code from a template injecting placeholders....

`python3 skellybobs.py -t template.yaml -o generated-src -p service=flipper -p group=bobsburgers -p adapter=http -p adapter=kafka`

### Introspecting existing code to generate template starters....

`python3 skellybobs.py --scan mycode --template-out mycode-template.yaml`

## Placeholder usage

* Placeholders in file or directory names e.g. `mypath/${service}/src`
* Placeholders in file contents (similarly)
* Render placeholders with initial caps (for Java classes)
* Placeholders can have multiple values to duplicate blocks using them (e.g. for adapters)
* Conditional codeblocks (based on placeholder values)

### Todo

* consistent spec for placeholders - probably use kebab-case as a base
* render placeholders as kebab-case, undercase or CamelCase with modifiers (e.g. $^{service})
