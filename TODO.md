# TODO

Version Compatibility
- [x] config.py: load via schema defaults so an old config.json won't crash on upgrade
- [x] db.py: Any change won't cause failed

Model Compatibility
- [ ] model_info: Any model will work with the latest model info

Agent
- [ ] outline: three-stage pipeline (split → per-section deep read → merge)
- [ ] outline chunking: for long transcripts
- [ ] self-evolution slow loop: prompt rewriting gated by feedback replay
- [ ] domains

- [ ] prompt: put into a single file