document.addEventListener('DOMContentLoaded', function () {
  const canvas = document.getElementById('bgCanvas');
  if (!canvas) return;

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 1000);
  const renderer = new THREE.WebGLRenderer({ canvas: canvas, alpha: true, antialias: true });

  renderer.setSize(window.innerWidth, window.innerHeight);
  renderer.setClearColor(0x000000, 0);
  renderer.setPixelRatio(window.devicePixelRatio);

  const buildingColors = [0x00f3ff, 0xff00ff, 0x0066ff];
  const buildings = [];

  for (let i = 0; i < 20; i++) {
    const w = 2 + Math.random() * 3;
    const h = 10 + Math.random() * 20;
    const d = 2 + Math.random() * 3;
    const geo = new THREE.BoxGeometry(w, h, d);
    const mat = new THREE.MeshBasicMaterial({
      color: buildingColors[i % buildingColors.length],
      wireframe: true,
      transparent: true,
      opacity: 0.3,
    });
    const mesh = new THREE.Mesh(geo, mat);
    mesh.position.set(
      (Math.random() - 0.5) * 80,
      (Math.random() - 0.5) * 20,
      (Math.random() - 0.5) * 80
    );
    scene.add(mesh);
    buildings.push(mesh);
  }

  const streams = [];
  for (let i = 0; i < 10; i++) {
    const points = [];
    const x = (Math.random() - 0.5) * 60;
    const z = (Math.random() - 0.5) * 60;
    for (let j = 0; j < 20; j++) {
      points.push(x, j * 2 - 20, z);
    }
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.Float32BufferAttribute(points, 3));
    const colors = [];
    for (let j = 0; j < 20; j++) {
      const c = new THREE.Color(buildingColors[j % buildingColors.length]);
      colors.push(c.r, c.g, c.b);
    }
    geo.setAttribute('color', new THREE.Float32BufferAttribute(colors, 3));
    const mat = new THREE.LineBasicMaterial({ vertexColors: true, transparent: true, opacity: 0.5 });
    const line = new THREE.LineSegments(geo, mat);
    scene.add(line);
    streams.push(line);
  }

  const panels = [];
  for (let i = 0; i < 5; i++) {
    const geo = new THREE.PlaneGeometry(10, 10);
    const mat = new THREE.MeshBasicMaterial({
      color: buildingColors[i % buildingColors.length],
      side: THREE.DoubleSide,
      transparent: true,
      opacity: 0.2,
    });
    const mesh = new THREE.Mesh(geo, mat);
    mesh.position.set(
      (Math.random() - 0.5) * 60,
      (Math.random() - 0.5) * 20,
      (Math.random() - 0.5) * 60
    );
    mesh.rotation.set(Math.random() * Math.PI, Math.random() * Math.PI, Math.random() * Math.PI);
    scene.add(mesh);
    panels.push(mesh);
  }

  const particleCount = 5000;
  const positions = new Float32Array(particleCount * 3);
  const pColors = new Float32Array(particleCount * 3);
  const cyanColor = new THREE.Color(0x00f3ff);
  const magentaColor = new THREE.Color(0xff00ff);

  for (let i = 0; i < particleCount; i++) {
    positions[i * 3]     = (Math.random() - 0.5) * 100;
    positions[i * 3 + 1] = (Math.random() - 0.5) * 100;
    positions[i * 3 + 2] = (Math.random() - 0.5) * 100;
    const c = i % 2 === 0 ? cyanColor : magentaColor;
    pColors[i * 3]     = c.r;
    pColors[i * 3 + 1] = c.g;
    pColors[i * 3 + 2] = c.b;
  }

  const particleGeo = new THREE.BufferGeometry();
  particleGeo.setAttribute('position', new THREE.BufferAttribute(positions, 3));
  particleGeo.setAttribute('color', new THREE.BufferAttribute(pColors, 3));
  const particleMat = new THREE.PointsMaterial({
    size: 0.1,
    vertexColors: true,
    blending: THREE.AdditiveBlending,
    transparent: true,
  });
  const particles = new THREE.Points(particleGeo, particleMat);
  scene.add(particles);

  camera.position.z = 30;

  let frame = 0;

  function animate() {
    requestAnimationFrame(animate);
    frame++;

    buildings.forEach((b, i) => {
      b.rotation.y += 0.001 * (i % 2 === 0 ? 1 : -1);
    });

    streams.forEach((s, i) => {
      s.position.y = Math.sin(frame * 0.01 + i) * 3;
    });

    panels.forEach((p, i) => {
      p.rotation.x += 0.003;
      p.rotation.y += 0.002;
      p.material.opacity = 0.1 + 0.1 * Math.abs(Math.sin(frame * 0.02 + i));
    });

    particles.rotation.y += 0.0005;
    const pos = particleGeo.attributes.position.array;
    for (let i = 0; i < particleCount; i++) {
      pos[i * 3 + 1] += Math.sin(frame * 0.01 + i * 0.1) * 0.005;
    }
    particleGeo.attributes.position.needsUpdate = true;

    renderer.render(scene, camera);
  }

  animate();

  window.addEventListener('resize', function () {
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(window.innerWidth, window.innerHeight);
  });
});
