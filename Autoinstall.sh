#!/usr/bin/env bash
set -euo pipefail

echo "🧰 1. Update system and install git"
sudo pacman -Syu --needed git base-devel vim sddm

echo "📁 2. Clone the dusky repo (if not already done)"
if [[ ! -d "$HOME/dusky" ]]; then
    git clone https://github.com/moukhtar22/dusky.git "$HOME/dusky"
fi

echo "📦 3. Deploy dotfiles using bare repo method"
git clone --bare --depth 1 https://github.com/moukhtar22/dusky.git "$HOME/.duskybare"
git --git-dir="$HOME/.duskybare/" --work-tree="$HOME" checkout -f

echo "📌 4. Create setup script folder if missing"
mkdir -p "$HOME/user_scripts/arch_setup_scripts/scripts"

echo "📜 5. Verify ORCHESTRA.sh exists"
if [[ ! -f "$HOME/dusky/user_scripts/arch_setup_scripts/ORCHESTRA.sh" ]]; then
    echo "❌ ORCHESTRA.sh not found!"
    exit 1
fi
chmod +x "$HOME/dusky/user_scripts/arch_setup_scripts/ORCHESTRA.sh"

echo "📃 6. Inspect and review the sequence of scripts to run"
echo "   → Looking inside the orchestrator:"
sed -n '1,60p' "$HOME/dusky/user_scripts/arch_setup_scripts/ORCHESTRA.sh"

echo "⚠️ 7. IMPORTANT: Copy or symlink helper scripts"
echo "   Make sure each script listed in INSTALL_SEQUENCE is in:"
echo "   $HOME/user_scripts/arch_setup_scripts/scripts/"
echo "   (Or update the SCRIPT_SEARCH_DIRS in ORCHESTRA.sh if needed)"

echo "✔️  Done. You can now run:"
echo "   bash \"$HOME/dusky/user_scripts/arch_setup_scripts/ORCHESTRA.sh\""
