# Gateway IN/OUT

## FIX Parser

Quickfix is the most popular open source FIX engine, but will raise an error when installing
on macOS. Here's the 
[solution](https://stackoverflow.com/questions/74895819/quickfix-for-python-library-installation-fails-in-macos):

1. Download `quickfix-1.15.1.tar.gz` from https://pypi.org/project/quickfix
2. Unpack it and edit `C++/AtomicCount.h` file by uncomment line 155 and comment out line 170 below:
    ```cpp
    static int atomic_exchange_and_add(int * pw, int dv)
    {
      int r = *pw;
      *pw += dv;
      return r;
    
      // int r;
    
      // __asm__ __volatile__
      //   (
      //     "lock\n\t"
      //     "xadd %1, %0":
      //     "+m"(*pw), "=r"(r) : // outputs (%0, %1)
      //     "1"(dv) : // inputs (%2 == %1)
      //     "memory", "cc" // clobbers
      //   );
    
      // return r;
    }
    ```
3. Then run `pip3 install .` while inside `quickfix-1.15.1` folder.

## uv configuration for quickfix

Problem: Manually installed packages (like `quickfix`) disappear after running `uv sync` or `uv run`.

Root cause: `uv sync` enforces **exact environment matching**, it removes any package not declared in your lockfile. 
This is by design for reproducibility, but breaks workflows with manually installed packages.

### Debug Process

1. **First attempt:** `uv add ./dependency/quickfix-1.15.1`
   - Failed because uv tried to add it as a workspace member, expecting a `pyproject.toml`

2. **Second attempt:** Build a wheel first, then add it
   ```zsh
   pip wheel . --no-deps -w dist/
   ```
   - Initial failure: the previous command had polluted `pyproject.toml` with a workspace member entry
   - After removing that entry, `uv add ./dependency/quickfix-1.15.1/dist/quickfix-1.15.1-*.whl` succeeded

### Solution
Reference the pre-built wheel directly:
```toml
[tool.uv.sources]
quickfix = { path = "dependency/quickfix-1.15.1/dist/quickfix-1.15.1-cp311-cp311-macosx_13_0_arm64.whl" }
```

### Principles

1. **uv is declarative**—everything must be in `pyproject.toml` and the lockfile. No "side installs" survive.

2. **Legacy packages without `pyproject.toml`** can't be added as source directories; you need a built wheel.

3. **Failed commands can leave state**—always check `pyproject.toml` for leftover entries after errors.

4. **Workarounds exist** (`--inexact`, `--no-sync`) but the cleanest fix is making the dependency explicit.