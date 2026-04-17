# CrossExtend-KG Scripts

This directory keeps only utility scripts that remain useful for the main architecture.

## visualize_propagation.py

Visualize propagation chains from exported graph artifacts.

### Usage

```bash
# Show propagation chains for CNC domain
python scripts/visualize_propagation.py \
  --domain cnc \
  --artifact-root artifacts/persistent_run-20260414T185408Z/full_llm/working

# Generate Graphviz DOT file
python scripts/visualize_propagation.py \
  --domain cnc \
  --output-dot propagation.dot
dot -Tpng propagation.dot -o propagation.png
```

### Outputs

- ASCII tree visualization of propagation chains
- Optional Graphviz DOT file for graphical rendering
