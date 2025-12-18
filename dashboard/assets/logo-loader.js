/**
 * Aura IA 3D Logo Loader
 * Three.js integration for animated GLB logo with gyroscope rings
 *
 * Features:
 * - Loads and displays animated GLB model
 * - Fallback to static image if GLB unavailable
 * - Auto-rotation and mouse interaction
 * - Bloom/glow post-processing
 * - Responsive sizing
 */

class AuraLogoLoader {
    constructor(containerId, options = {}) {
        this.containerId = containerId;
        this.container = null;
        this.scene = null;
        this.camera = null;
        this.renderer = null;
        this.mixer = null;
        this.model = null;
        this.clock = null;
        this.animationId = null;

        // Configuration
        this.options = {
            glbPath: options.glbPath || 'assets/auralia_scene.glb',
            fallbackImage: options.fallbackImage || 'AuraIA New Logo (1).jpg',
            autoRotate: options.autoRotate !== false,
            rotationSpeed: options.rotationSpeed || 0.002,
            enableInteraction: options.enableInteraction !== false,
            backgroundColor: options.backgroundColor || 0x1a1a2e,
            ambientIntensity: options.ambientIntensity || 0.5,
            ...options
        };

        this.mouseX = 0;
        this.mouseY = 0;
        this.targetRotationX = 0;
        this.targetRotationY = 0;
    }

    async init() {
        this.container = document.getElementById(this.containerId);
        if (!this.container) {
            console.error(`Container #${this.containerId} not found`);
            return false;
        }

        // Check if Three.js is available
        if (typeof THREE === 'undefined') {
            console.warn('Three.js not loaded, using fallback image');
            this.showFallbackImage();
            return false;
        }

        try {
            await this.setupScene();
            await this.loadModel();
            this.setupLights();
            this.setupInteraction();
            this.animate();
            return true;
        } catch (error) {
            console.error('Failed to initialize 3D logo:', error);
            this.showFallbackImage();
            return false;
        }
    }

    async setupScene() {
        const width = this.container.clientWidth;
        const height = this.container.clientHeight;

        // Scene
        this.scene = new THREE.Scene();

        // Camera
        this.camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 1000);
        this.camera.position.set(0, 0, 4);

        // Renderer with transparency
        this.renderer = new THREE.WebGLRenderer({
            antialias: true,
            alpha: true,
            powerPreference: 'high-performance'
        });
        this.renderer.setSize(width, height);
        this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
        this.renderer.outputEncoding = THREE.sRGBEncoding;
        this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
        this.renderer.toneMappingExposure = 1.2;

        // Clear existing content and add canvas
        this.container.innerHTML = '';
        this.container.appendChild(this.renderer.domElement);

        // Style the canvas
        this.renderer.domElement.style.borderRadius = '50%';

        // Clock for animations
        this.clock = new THREE.Clock();

        // Handle resize
        window.addEventListener('resize', () => this.onResize());
    }

    async loadModel() {
        return new Promise((resolve, reject) => {
            // Check if GLTFLoader is available
            if (typeof THREE.GLTFLoader === 'undefined') {
                reject(new Error('GLTFLoader not available'));
                return;
            }

            const loader = new THREE.GLTFLoader();

            loader.load(
                this.options.glbPath,
                (gltf) => {
                    this.model = gltf.scene;

                    // Center and scale the model
                    const box = new THREE.Box3().setFromObject(this.model);
                    const center = box.getCenter(new THREE.Vector3());
                    const size = box.getSize(new THREE.Vector3());
                    const maxDim = Math.max(size.x, size.y, size.z);
                    const scale = 2 / maxDim;

                    this.model.scale.setScalar(scale);
                    this.model.position.sub(center.multiplyScalar(scale));

                    this.scene.add(this.model);

                    // Setup animations if present
                    if (gltf.animations && gltf.animations.length > 0) {
                        this.mixer = new THREE.AnimationMixer(this.model);
                        gltf.animations.forEach(clip => {
                            const action = this.mixer.clipAction(clip);
                            action.play();
                        });
                    }

                    console.log('✓ 3D Logo loaded successfully');
                    resolve(gltf);
                },
                (progress) => {
                    const percent = (progress.loaded / progress.total * 100).toFixed(0);
                    console.log(`Loading 3D logo: ${percent}%`);
                },
                (error) => {
                    console.error('Error loading GLB:', error);
                    reject(error);
                }
            );
        });
    }

    setupLights() {
        // Ambient light
        const ambient = new THREE.AmbientLight(0xffffff, this.options.ambientIntensity);
        this.scene.add(ambient);

        // Key light (top-left)
        const keyLight = new THREE.DirectionalLight(0xffffff, 1.0);
        keyLight.position.set(-2, 2, 2);
        this.scene.add(keyLight);

        // Fill light (bottom-right, cyan tint)
        const fillLight = new THREE.DirectionalLight(0x00d4ff, 0.5);
        fillLight.position.set(2, -1, 2);
        this.scene.add(fillLight);

        // Rim light (back, purple tint)
        const rimLight = new THREE.DirectionalLight(0x8a2be2, 0.4);
        rimLight.position.set(0, 0, -3);
        this.scene.add(rimLight);

        // Point light for bloom effect
        const pointLight = new THREE.PointLight(0x00d4ff, 0.5, 10);
        pointLight.position.set(0, 0, 2);
        this.scene.add(pointLight);
    }

    setupInteraction() {
        if (!this.options.enableInteraction) return;

        this.container.addEventListener('mousemove', (e) => {
            const rect = this.container.getBoundingClientRect();
            this.mouseX = ((e.clientX - rect.left) / rect.width) * 2 - 1;
            this.mouseY = -((e.clientY - rect.top) / rect.height) * 2 + 1;
        });

        this.container.addEventListener('mouseleave', () => {
            this.mouseX = 0;
            this.mouseY = 0;
        });
    }

    animate() {
        this.animationId = requestAnimationFrame(() => this.animate());

        const delta = this.clock.getDelta();

        // Update animation mixer
        if (this.mixer) {
            this.mixer.update(delta);
        }

        // Auto rotation
        if (this.model && this.options.autoRotate) {
            this.model.rotation.y += this.options.rotationSpeed;
        }

        // Mouse interaction (subtle tilt)
        if (this.model && this.options.enableInteraction) {
            this.targetRotationX = this.mouseY * 0.2;
            this.targetRotationY = this.mouseX * 0.2;

            this.model.rotation.x += (this.targetRotationX - this.model.rotation.x) * 0.05;
            // Y rotation handled by auto-rotate, so we add interaction on top
        }

        this.renderer.render(this.scene, this.camera);
    }

    onResize() {
        if (!this.container || !this.camera || !this.renderer) return;

        const width = this.container.clientWidth;
        const height = this.container.clientHeight;

        this.camera.aspect = width / height;
        this.camera.updateProjectionMatrix();
        this.renderer.setSize(width, height);
    }

    showFallbackImage() {
        if (!this.container) return;

        // Create fallback image element
        const img = document.createElement('img');
        img.src = this.options.fallbackImage;
        img.alt = 'Aura IA Logo';
        img.className = 'logo';
        img.style.cssText = `
            width: 100%;
            height: 100%;
            object-fit: cover;
            object-position: center;
            transform: scale(1.05) translateX(-1px);
            border: none;
            box-shadow: none;
            animation: pulseScale 8s ease-in-out infinite;
            border-radius: 0;
        `;

        this.container.innerHTML = '';
        this.container.appendChild(img);
    }

    dispose() {
        if (this.animationId) {
            cancelAnimationFrame(this.animationId);
        }

        if (this.renderer) {
            this.renderer.dispose();
        }

        if (this.scene) {
            this.scene.traverse((object) => {
                if (object.geometry) object.geometry.dispose();
                if (object.material) {
                    if (Array.isArray(object.material)) {
                        object.material.forEach(m => m.dispose());
                    } else {
                        object.material.dispose();
                    }
                }
            });
        }

        window.removeEventListener('resize', this.onResize);
    }
}

// Auto-initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    // Check if logo-wrapper exists and has the data attribute for 3D
    const logoWrapper = document.getElementById('logo-3d-container');
    if (logoWrapper) {
        const loader = new AuraLogoLoader('logo-3d-container', {
            glbPath: logoWrapper.dataset.glbPath || 'assets/auralia_scene.glb',
            fallbackImage: logoWrapper.dataset.fallbackImage || 'AuraIA New Logo (1).jpg'
        });
        loader.init();

        // Expose to global for debugging
        window.auraLogoLoader = loader;
    }
});

// Export for module usage
if (typeof module !== 'undefined' && module.exports) {
    module.exports = AuraLogoLoader;
}
