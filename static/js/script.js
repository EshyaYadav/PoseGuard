document.addEventListener("DOMContentLoaded", function () {
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 1000);
    const renderer = new THREE.WebGLRenderer({ 
        canvas: document.getElementById("bgCanvas"),
        alpha: true,
        antialias: true
    });

    renderer.setSize(window.innerWidth, window.innerHeight);
    renderer.setClearColor(0x000000, 0);
    renderer.setPixelRatio(window.devicePixelRatio);
    document.body.appendChild(renderer.domElement);

    // Create cyberpunk buildings
    const buildings = [];
    const buildingColors = [0x00f3ff, 0xff00ff, 0x0066ff];
    
    for (let i = 0; i < 20; i++) {
        const width = 2 + Math.random() * 3;
        const height = 10 + Math.random() * 20;
        const depth = 2 + Math.random() * 3;
        
        const geometry = new THREE.BoxGeometry(width, height, depth);
        const material = new THREE.MeshBasicMaterial({
            color: buildingColors[Math.floor(Math.random() * buildingColors.length)],
            wireframe: true,
            transparent: true,
            opacity: 0.3
        });
        
        const building = new THREE.Mesh(geometry, material);
        building.position.x = (Math.random() - 0.5) * 100;
        building.position.y = height / 2 - 10;
        building.position.z = (Math.random() - 0.5) * 100;
        
        buildings.push(building);
        scene.add(building);
    }

    // Create holographic data streams
    const dataStreams = [];
    const streamGeometry = new THREE.BufferGeometry();
    const streamCount = 10;
    const streamPositions = new Float32Array(streamCount * 6);
    const streamColors = new Float32Array(streamCount * 6);

    for (let i = 0; i < streamCount; i++) {
        const startX = (Math.random() - 0.5) * 100;
        const startY = -10 + Math.random() * 20;
        const startZ = (Math.random() - 0.5) * 100;
        
        streamPositions[i * 6] = startX;
        streamPositions[i * 6 + 1] = startY;
        streamPositions[i * 6 + 2] = startZ;
        streamPositions[i * 6 + 3] = startX;
        streamPositions[i * 6 + 4] = startY + 30;
        streamPositions[i * 6 + 5] = startZ;

        const color = buildingColors[Math.floor(Math.random() * buildingColors.length)];
        streamColors[i * 6] = ((color >> 16) & 255) / 255;
        streamColors[i * 6 + 1] = ((color >> 8) & 255) / 255;
        streamColors[i * 6 + 2] = (color & 255) / 255;
        streamColors[i * 6 + 3] = ((color >> 16) & 255) / 255;
        streamColors[i * 6 + 4] = ((color >> 8) & 255) / 255;
        streamColors[i * 6 + 5] = (color & 255) / 255;
    }

    streamGeometry.setAttribute('position', new THREE.BufferAttribute(streamPositions, 3));
    streamGeometry.setAttribute('color', new THREE.BufferAttribute(streamColors, 3));

    const streamMaterial = new THREE.LineBasicMaterial({
        vertexColors: true,
        transparent: true,
        opacity: 0.5
    });

    const streamMesh = new THREE.LineSegments(streamGeometry, streamMaterial);
    scene.add(streamMesh);

    // Create holographic panels
    const panels = [];
    for (let i = 0; i < 5; i++) {
        const panelGeometry = new THREE.PlaneGeometry(10, 10);
        const panelMaterial = new THREE.MeshBasicMaterial({
            color: buildingColors[Math.floor(Math.random() * buildingColors.length)],
            transparent: true,
            opacity: 0.2,
            side: THREE.DoubleSide
        });
        
        const panel = new THREE.Mesh(panelGeometry, panelMaterial);
        panel.position.x = (Math.random() - 0.5) * 100;
        panel.position.y = Math.random() * 20;
        panel.position.z = (Math.random() - 0.5) * 100;
        panel.rotation.x = Math.random() * Math.PI;
        panel.rotation.y = Math.random() * Math.PI;
        
        panels.push(panel);
        scene.add(panel);
    }

    // Create floating particles with cyberpunk colors
    const particlesGeometry = new THREE.BufferGeometry();
    const particlesCount = 5000;
    const posArray = new Float32Array(particlesCount * 3);
    const colorArray = new Float32Array(particlesCount * 3);

    for (let i = 0; i < particlesCount * 3; i += 3) {
        posArray[i] = (Math.random() - 0.5) * 100;
        posArray[i + 1] = (Math.random() - 0.5) * 100;
        posArray[i + 2] = (Math.random() - 0.5) * 100;

        const color = Math.random() < 0.5 ? 0x00f3ff : 0xff00ff;
        colorArray[i] = ((color >> 16) & 255) / 255;
        colorArray[i + 1] = ((color >> 8) & 255) / 255;
        colorArray[i + 2] = (color & 255) / 255;
    }

    particlesGeometry.setAttribute('position', new THREE.BufferAttribute(posArray, 3));
    particlesGeometry.setAttribute('color', new THREE.BufferAttribute(colorArray, 3));
    
    const particlesMaterial = new THREE.PointsMaterial({
        size: 0.1,
        vertexColors: true,
        transparent: true,
        opacity: 0.8,
        blending: THREE.AdditiveBlending
    });
    
    const particlesMesh = new THREE.Points(particlesGeometry, particlesMaterial);
    scene.add(particlesMesh);

    camera.position.z = 30;

    // Animation
    function animate() {
        requestAnimationFrame(animate);

        // Animate buildings
        buildings.forEach((building, index) => {
            building.rotation.y += 0.001;
            building.position.y = building.position.y + Math.sin(Date.now() * 0.001 + index) * 0.05;
        });

        // Animate data streams
        const streamPositions = streamMesh.geometry.attributes.position.array;
        for (let i = 0; i < streamCount; i++) {
            const offset = i * 6;
            streamPositions[offset + 1] = -10 + Math.sin(Date.now() * 0.001 + i) * 5;
            streamPositions[offset + 4] = 20 + Math.sin(Date.now() * 0.001 + i) * 5;
        }
        streamMesh.geometry.attributes.position.needsUpdate = true;

        // Animate holographic panels
        panels.forEach((panel, index) => {
            panel.rotation.x += 0.001;
            panel.rotation.y += 0.001;
            panel.position.y = panel.position.y + Math.sin(Date.now() * 0.001 + index) * 0.1;
            panel.material.opacity = 0.2 + Math.sin(Date.now() * 0.001 + index) * 0.1;
        });

        // Animate particles with wave effect
        particlesMesh.rotation.y += 0.0005;
        const positions = particlesMesh.geometry.attributes.position.array;
        for (let i = 0; i < positions.length; i += 3) {
            positions[i + 1] += Math.sin(Date.now() * 0.001 + i) * 0.01;
        }
        particlesMesh.geometry.attributes.position.needsUpdate = true;

        renderer.render(scene, camera);
    }

    // Handle window resize
    window.addEventListener('resize', () => {
        camera.aspect = window.innerWidth / window.innerHeight;
        camera.updateProjectionMatrix();
        renderer.setSize(window.innerWidth, window.innerHeight);
    });

    animate();
});