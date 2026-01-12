#!/bin/bash

# Directory setup
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
TEMPLATE_DIR="${SCRIPT_DIR}/../templates"
GENERATED_DIR="${SCRIPT_DIR}/../generated"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Ensure the generated directory exists
mkdir -p "${GENERATED_DIR}"

# Function to generate a random string
generate_random_string() {
    local length=$1
    openssl rand -base64 $length | tr -dc 'a-zA-Z0-9' | head -c $length
}

# Function to generate a bcrypt hash
generate_bcrypt_hash() {
    local password=$1
    # Use the virtual environment's Python from the project root
    ../../../.venv/bin/python -c "import bcrypt; print(bcrypt.hashpw('$password'.encode('utf-8'), bcrypt.gensalt()).decode('utf-8'))"
}

# Function to generate a PostgreSQL SCRAM-SHA-256 password
generate_postgres_password() {
    local length=12
    local password=$(openssl rand -base64 $length | tr -dc 'a-zA-Z0-9._' | head -c $length)
    echo "$password"
}

# Function to replace placeholders in a template
replace_placeholders() {
    local template=$1
    local output=$2
    
    # Copy template to output
    cp "$template" "$output"
    
    # Read the template and find all placeholders
    placeholders=$(grep -o '__[A-Z_]*__' "$template" | sort -u)
    
    # For each placeholder, ask for a value
    for placeholder in $placeholders; do
        # Skip optional placeholders
        if grep -q "#_OPTIONAL_.*$placeholder" "$template"; then
            echo -e "${YELLOW}Optional placeholder found: $placeholder${NC}"
            read -p "Do you want to set this value? (y/N) " answer
            if [[ "$answer" != "y" ]]; then
                # Comment out the line containing the optional placeholder
                sed -i '' "/#_OPTIONAL_.*$placeholder/d" "$output"
                continue
            fi
        fi
        
        # Remove the #_OPTIONAL_ prefix if it exists
        sed -i '' "s/#_OPTIONAL_ //" "$output"
        
        # Special handling for different types of secrets
        case $placeholder in
            "__REDIS_PASSWORD__")
                value=$(generate_random_string 32)
                echo -e "${GREEN}Generated Redis password${NC}"
                ;;
            "__ADMIN_PASSWORD_HASH__")
                read -s -p "Enter admin password: " password
                echo
                value=$(generate_bcrypt_hash "$password")
                echo -e "${GREEN}Generated password hash${NC}"
                ;;
            "__SERVER_SECRET_KEY__")
                value=$(generate_random_string 32)
                echo -e "${GREEN}Generated server secret key${NC}"
                ;;
            "__POSTGRES_PASSWORD__")
                read -s -p "Enter PostgreSQL password: " value
                echo
                echo -e "${GREEN}Password set for PostgreSQL${NC}"
                ;;
            "__GRAFANA_ADMIN_USER__")
                read -p "Enter Grafana admin user [admin]: " value
                value=${value:-admin}
                ;;
            "__GRAFANA_ADMIN_PASSWORD__")
                read -s -p "Enter Grafana admin password: " value
                echo
                ;;
            "__GRAFANA_SECRET_KEY__")
                value=$(generate_random_string 48)
                echo -e "${GREEN}Generated random key for $placeholder${NC}"
                ;;
            *)
                read -p "Enter value for $placeholder: " value
                ;;
        esac
        
        # Replace the placeholder in the output file
        sed -i '' "s|$placeholder|$value|g" "$output"
    done
}

# Main script
echo -e "${GREEN}Secret Generator${NC}"
echo "Available templates:"
ls -1 "${TEMPLATE_DIR}" | grep "\.template\.yaml$" | cat -n

read -p "Select template number: " template_number
template_file=$(ls -1 "${TEMPLATE_DIR}" | grep "\.template\.yaml$" | sed -n "${template_number}p")

if [ -z "$template_file" ]; then
    echo -e "${RED}Invalid template number${NC}"
    exit 1
fi

output_file="${GENERATED_DIR}/${template_file/.template/}"
echo -e "${GREEN}Generating ${output_file}${NC}"

replace_placeholders "${TEMPLATE_DIR}/${template_file}" "$output_file"

# Auto-apply logic
# --- al final, en el auto-apply: añade estos casos ---
case "$output_file" in
  *web-crawler.yaml)
    echo -e "${GREEN}Applying $output_file to namespace 'default'...${NC}"
    kubectl apply -f "$output_file" -n default
    ;;
  *openwebui.yaml)
    echo -e "${GREEN}Applying $output_file to namespace 'default'...${NC}"
    kubectl apply -f "$output_file" -n default
    ;;
  *postgres.yaml|*redis.yaml)
    echo -e "${GREEN}Applying $output_file to namespaces 'default' and 'shared'...${NC}"
    kubectl apply -f "$output_file" -n shared
    ;;
  *argocd.yaml)
    echo -e "${GREEN}Applying $output_file to namespace 'argocd'...${NC}"
    kubectl apply -f "$output_file" -n argocd
    ;;
  *grafana.yaml)
    echo -e "${GREEN}Applying $output_file to namespace 'observability'...${NC}"
    kubectl apply -f "$output_file" -n observability
    ;;
esac

echo -e "${GREEN}Secret generated successfully!${NC}"
echo "To apply the secret to your cluster, run:"
echo -e "${YELLOW}kubectl apply -f ${output_file}${NC}" 