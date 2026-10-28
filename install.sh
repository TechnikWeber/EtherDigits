#!/usr/bin/env bash
# EtherDigits installer for Linux (Fedora, Debian, Ubuntu, Raspberry Pi OS) and macOS.
#
#   curl -fsSL https://raw.githubusercontent.com/TechnikWeber/EtherDigits/main/install.sh | bash
#
# Options (append after "bash -s --" when piping):
#   --no-service          do not start EtherDigits in the background at login/boot
#   --no-system-packages  do not install PortAudio, ffmpeg and Hamlib (sound card, MP3/stream, CAT)
#   --with-hamlib         also install Hamlib for CAT control (rigctld)
#
# Run it as your normal user; it asks for sudo only to install system packages.
# Running it again updates EtherDigits and keeps all data.
set -euo pipefail

REPO="https://github.com/TechnikWeber/EtherDigits.git"
DIR="${ETHERDIGITS_APP:-$HOME/.local/share/etherdigits-app}"
SOURCE="${ETHERDIGITS_SOURCE:-}"   # a local checkout to copy instead of cloning (for testing)
SERVICE=1
SYSTEM=1
HAMLIB=0
for arg in "$@"; do
  case "$arg" in
    --no-service) SERVICE=0 ;;
    --no-system-packages) SYSTEM=0 ;;
    --with-hamlib) HAMLIB=1 ;;
    *) echo "Unknown option: $arg" >&2; exit 2 ;;
  esac
done

say()  { printf '\n\033[1m%s\033[0m\n' "$*"; }
warn() { printf '\033[33mWarning: %s\033[0m\n' "$*" >&2; }

if [ "$(id -u)" -eq 0 ]; then
  echo "Please run this as your normal user, not as root." >&2
  exit 1
fi

# --- system packages -------------------------------------------------------------
if [ "$SYSTEM" -eq 1 ]; then
  say "Installing system packages (PortAudio for the sound card, ffmpeg for MP3 and streaming)"
  if [ "$(uname)" = "Darwin" ]; then
    if command -v brew >/dev/null; then
      brew install python git portaudio ffmpeg || warn "brew could not install everything"
      [ "$HAMLIB" -eq 1 ] && { brew install hamlib || warn "Hamlib was not installed"; }
    else
      warn "Homebrew not found; install Python 3.10+, git and ffmpeg yourself (https://brew.sh)"
    fi
  elif command -v apt-get >/dev/null; then
    sudo apt-get update
    sudo apt-get install -y git python3 python3-venv libportaudio2 ffmpeg
    [ "$HAMLIB" -eq 1 ] && { sudo apt-get install -y libhamlib-utils || warn "Hamlib was not installed"; }
  elif command -v dnf >/dev/null; then
    sudo dnf install -y git python3 portaudio ffmpeg-free || sudo dnf install -y git python3 portaudio
    [ "$HAMLIB" -eq 1 ] && { sudo dnf install -y hamlib || warn "Hamlib was not installed"; }
  else
    warn "unknown package manager; install Python 3.10+, git, PortAudio and ffmpeg yourself"
  fi
fi

# --- Python --------------------------------------------------------------------------
PY=""
for candidate in python3.13 python3.12 python3.11 python3.10 python3; do
  if command -v "$candidate" >/dev/null && "$candidate" -c 'import sys; sys.exit(sys.version_info < (3, 10))'; then
    PY="$candidate"; break
  fi
done
[ -n "$PY" ] || { echo "Python 3.10 or newer is needed." >&2; exit 1; }

# --- the program -----------------------------------------------------------------
say "Fetching EtherDigits to $DIR"
if [ -n "$SOURCE" ]; then
  mkdir -p "$DIR"
  (cd "$SOURCE" && git ls-files -z) | (cd "$SOURCE" && xargs -0 tar cf -) | (cd "$DIR" && tar xf -)
elif [ -d "$DIR/.git" ]; then
  git -C "$DIR" pull --ff-only
else
  git clone --depth 1 "$REPO" "$DIR"
fi

say "Setting up Python packages"
[ -x "$DIR/.venv/bin/python" ] || "$PY" -m venv "$DIR/.venv"
"$DIR/.venv/bin/pip" install --quiet --upgrade pip
"$DIR/.venv/bin/pip" install --quiet -r "$DIR/requirements.txt"

mkdir -p "$HOME/.local/bin"
cat > "$HOME/.local/bin/etherdigits" <<EOF
#!/bin/sh
cd "$DIR" && exec "$DIR/.venv/bin/python" -m etherdigits "\$@"
EOF
chmod +x "$HOME/.local/bin/etherdigits"
case ":$PATH:" in *":$HOME/.local/bin:"*) ;; *) warn "$HOME/.local/bin is not in PATH; call $HOME/.local/bin/etherdigits" ;; esac

"$DIR/.venv/bin/python" -c 'import sounddevice' 2>/dev/null || warn "no PortAudio: the sound card output will not work until it is installed"

if [ "$SERVICE" -eq 1 ]; then
  say "Starting EtherDigits in the background"
  (cd "$DIR" && "$DIR/.venv/bin/python" -m etherdigits service install)
fi

say "Done."
echo "Open http://127.0.0.1:8472/ in a browser."
[ "$SERVICE" -eq 1 ] || echo "Start it with: etherdigits serve"
echo "Before reaching the station from another computer, set a password: etherdigits password"
