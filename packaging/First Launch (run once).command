#!/bin/bash
# First-launch helper for Briefing.
# The downloaded app isn't Apple-notarized, so macOS blocks the first launch.
# Double-click this once to clear the quarantine flag and open the app.
# After that you can just double-click Briefing normally.

APP=""
for c in "/Applications/Briefing.app" "$HOME/Applications/Briefing.app"; do
  [ -d "$c" ] && APP="$c" && break
done

if [ -z "$APP" ]; then
  echo "Briefing not found in Applications."
  echo "Drag Briefing from the disk image into the Applications folder first, then run this again."
  echo
  read -n 1 -s -r -p "Press any key to close..."
  exit 1
fi

echo "Removing download quarantine: $APP"
xattr -dr com.apple.quarantine "$APP" 2>/dev/null
echo "Launching Briefing..."
open "$APP"
echo "Done. You can double-click Briefing directly from now on."
sleep 2
