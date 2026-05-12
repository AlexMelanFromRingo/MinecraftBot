# Pushing this project to GitHub

After creating an empty repository on github.com/<your-account>/MinecraftBot,
run the following from this checkout to push everything and apply the
suggested topics and release.

```bash
# 1. Point this checkout at the new remote.
git remote add origin git@github.com:<your-account>/MinecraftBot.git

# 2. Push main + the 003 branch.
git push -u origin 003-rust-pyo3-bridge
git checkout -b main 003-rust-pyo3-bridge
git push -u origin main

# 3. Apply repo topics from .github/repo-topics.txt
gh repo edit <your-account>/MinecraftBot \
    --add-topic minecraft \
    --add-topic minecraft-java \
    --add-topic minecraft-protocol \
    --add-topic minecraft-bot \
    --add-topic bot \
    --add-topic agent-framework \
    --add-topic python \
    --add-topic rust \
    --add-topic pyo3 \
    --add-topic maturin \
    --add-topic asyncio \
    --add-topic tokio \
    --add-topic ml \
    --add-topic reinforcement-learning \
    --add-topic ai-agent \
    --add-topic protocol-763 \
    --add-topic paper \
    --add-topic voxel-world \
    --add-topic pathfinding \
    --add-topic abi3 \
    --add-topic wheels

# 4. Set the repo description.
gh repo edit <your-account>/MinecraftBot \
    --description "Minecraft Java Edition 1.20.1 bot framework. Three artefacts: Python reference, standalone Rust crate, PyO3 facade. Live-tested on Paper."

# 5. Tag and create the v0.2.0 release. The release.yml workflow
# triggers on the tag, builds wheels for 5 platforms, and uploads
# them to the release.
git tag -a v0.2.0 -m "v0.2.0: first PyO3 facade release"
git push origin v0.2.0

# 6. After wheels.yml completes, check release assets:
gh release view v0.2.0 --json assets --jq '.assets[].name'
```

## CI badges

Once the repo is up and the CI has run once, add these to README.md
(replace `<your-account>`):

```markdown
[![CI](https://github.com/<your-account>/MinecraftBot/actions/workflows/ci.yml/badge.svg)](https://github.com/<your-account>/MinecraftBot/actions/workflows/ci.yml)
[![Wheels](https://github.com/<your-account>/MinecraftBot/actions/workflows/wheels.yml/badge.svg)](https://github.com/<your-account>/MinecraftBot/actions/workflows/wheels.yml)
```
