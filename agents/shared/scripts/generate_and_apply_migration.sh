#!/bin/bash
set -e

# Script's own directory
_SCRIPT_DIR_TEMP="$(dirname "$0")"
cd "$_SCRIPT_DIR_TEMP" # Ensure we are in the script's directory first
SCRIPT_DIR="$(pwd)"      # Get absolute path to script's dir
cd - > /dev/null         # Go back to original CWD

# Path to the existing run_migrations.sh script
RUN_MIGRATIONS_SCRIPT="$SCRIPT_DIR/run_migrations.sh"

if [ $# -eq 0 ]; then
  echo "Usage: $0 \"migration message\" [--no-apply]"
  echo "Example: $0 \"add new user fields\""
  echo "  --no-apply : Only generates the migration, does not apply it."
  exit 1
fi

MIGRATION_MESSAGE="$1"
APPLY_MIGRATION=true

if [ "$2" == "--no-apply" ]; then
  APPLY_MIGRATION=false
fi

# Ensure run_migrations.sh is executable
if [ ! -x "$RUN_MIGRATIONS_SCRIPT" ]; then
  echo "Error: $RUN_MIGRATIONS_SCRIPT is not executable. Please run: chmod +x $RUN_MIGRATIONS_SCRIPT" >&2
  exit 1
fi

# Step 1: Generate the migration script
echo ""
echo "--- Generating migration script --- "
"$RUN_MIGRATIONS_SCRIPT" revision --autogenerate -m "$MIGRATION_MESSAGE"

if [ "$APPLY_MIGRATION" = true ] ; then
  # Step 2: Ask for confirmation to apply
  echo ""
echo "--- Migration script generated. Please review it carefully before applying. --- "
  read -p "Do you want to apply this migration now? (yes/no): " confirmation

  if [[ "$confirmation" == "yes" || "$confirmation" == "y" ]]; then
    # Step 3: Apply the migration
    echo ""
    echo "--- Applying migration --- "
    "$RUN_MIGRATIONS_SCRIPT" upgrade head
    echo ""
    echo "--- Migration applied successfully. --- "
  else
    echo "Migration not applied. You can apply it manually later using: $RUN_MIGRATIONS_SCRIPT upgrade head"
  fi
else
  echo ""
  echo "--- Migration script generated but not applied (due to --no-apply flag). --- "
  echo "You can review it and apply it manually later using: $RUN_MIGRATIONS_SCRIPT upgrade head"
fi

echo ""
echo "Process complete." 