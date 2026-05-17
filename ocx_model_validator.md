## OCX Model Validator package

The ocx_model_validator is a Python module for validating OCX .3docx model files against the OCX IR schema. It checks for structural correctness, required fields, and basic semantic consistency. This helps ensure that models can be successfully parsed and used for downstream processing or agents.

### Project Structure
```
ocx_model_validator/
├── __init__.py
├── model               # OCX Intermediate Representation dataclasses
   ├── ir.py                # IrVessel, IrPanel, IrUnit, etc.
   └── units.py             # UnitConverter, build_unit_registry
├── builders            # Builders to convert from .3docx to OCX IR
    ├── base.py             # AbstractBuilder interface
    ├── factory.py          # get_builder(schema_version) → builder
    └── v3_builder.py       # Builder for OCX schema version 3.0
├── parsers               # OCX parsers to read .3docx files 
    ├── base_parser.py      # Abstract Parser interface
    ├── parser.py       # OcxParser: reads .3docx, 
    └── dynamic_loader.py   # Dynamically load OCX dataclasses
    
├── tests     # Unit tests 
    ├── __init__.py

```
### OCX Intermediate Representation (IR)
The OCX IR is a schema-neutral, Python dataclass-based representation of the core concepts in an OCX model. It includes entities like IrVessel, IrPanel, IrUnit, etc., which capture the essential information from the .3docx files in a structured way. 
The IR serves as a common format for builders to convert from different schema versions into a consistent internal representation.
IR capture OCX metadata, vessel particulars, panel definitions, material properties, and unit definitions. This allows for flexible querying and validation of the model content without being tied to a specific OCX schema version.
OCX geometry is not part of current scope, but can come later.

