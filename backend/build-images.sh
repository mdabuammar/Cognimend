#!/usr/bin/env bash
# =============================================================================
# DriftGuard Docker Build Script
# =============================================================================
# Builds all microservice Docker images with proper tagging and optimization.
#
# Usage:
#   ./build-images.sh                    # Build all with :latest tag
#   ./build-images.sh v1.2.3             # Build all with specific version
#   ./build-images.sh v1.2.3 controller  # Build specific service
#
# =============================================================================

set -euo pipefail

# Configuration
REGISTRY="${REGISTRY:-ghcr.io/driftguard}"
VERSION="${1:-latest}"
SERVICE="${2:-all}"
BUILD_DATE=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
VCS_REF=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Services to build
SERVICES=(
    "controller:8005"
    "query:8002"
    "upload:8001"
    "evaluation:8003"
    "drift_detector:8004"
    "telemetry:8006"
)

# Function to build a single service
build_service() {
    local service_name=$1
    local port=$2
    local dockerfile="services/${service_name}/Dockerfile.optimized"
    local image_name="${REGISTRY}/${service_name}:${VERSION}"
    
    echo -e "${YELLOW}Building ${service_name}...${NC}"
    
    if [ ! -f "$dockerfile" ]; then
        echo -e "${RED}Dockerfile not found: $dockerfile${NC}"
        echo -e "${YELLOW}Falling back to standard Dockerfile${NC}"
        dockerfile="services/${service_name}/Dockerfile"
    fi
    
    docker build \
        --file "$dockerfile" \
        --tag "$image_name" \
        --tag "${REGISTRY}/${service_name}:latest" \
        --build-arg BUILD_VERSION="$VERSION" \
        --build-arg BUILD_DATE="$BUILD_DATE" \
        --build-arg VCS_REF="$VCS_REF" \
        --cache-from "${REGISTRY}/${service_name}:latest" \
        --label "org.opencontainers.image.created=$BUILD_DATE" \
        --label "org.opencontainers.image.revision=$VCS_REF" \
        --label "org.opencontainers.image.version=$VERSION" \
        .
    
    echo -e "${GREEN}✓ Built $image_name${NC}"
}

# Function to push images
push_service() {
    local service_name=$1
    local image_name="${REGISTRY}/${service_name}:${VERSION}"
    
    echo -e "${YELLOW}Pushing ${service_name}...${NC}"
    
    docker push "$image_name"
    docker push "${REGISTRY}/${service_name}:latest"
    
    echo -e "${GREEN}✓ Pushed $image_name${NC}"
}

# Main execution
echo "=============================================="
echo "DriftGuard Docker Build"
echo "=============================================="
echo "Registry: $REGISTRY"
echo "Version: $VERSION"
echo "Build Date: $BUILD_DATE"
echo "VCS Ref: $VCS_REF"
echo "=============================================="

cd "$(dirname "$0")"

# Build services
if [ "$SERVICE" = "all" ]; then
    for service_info in "${SERVICES[@]}"; do
        IFS=':' read -r service_name port <<< "$service_info"
        build_service "$service_name" "$port"
    done
else
    # Build specific service
    for service_info in "${SERVICES[@]}"; do
        IFS=':' read -r service_name port <<< "$service_info"
        if [ "$service_name" = "$SERVICE" ]; then
            build_service "$service_name" "$port"
            break
        fi
    done
fi

echo ""
echo -e "${GREEN}=============================================="
echo "Build Complete!"
echo "==============================================${NC}"

# Show image sizes
echo ""
echo "Image Sizes:"
docker images --filter "reference=${REGISTRY}/*:${VERSION}" --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}"
