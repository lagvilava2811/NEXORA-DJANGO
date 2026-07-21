export const simulationVertex = `
    varying vec2 vUv;
    void main() {
        vUv = uv;
        gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
    }
`;

export const simulationFragment = `
    precision highp float;
    uniform sampler2D u_posTexture;
    uniform sampler2D u_targetPos;
    uniform float u_time;
    uniform vec2 u_mouse;
    uniform float u_audio;
    uniform float u_explosion;
    varying vec2 vUv;

    vec4 permute(vec4 x){return mod(((x*34.0)+1.0)*x, 289.0);}
    vec4 taylorInvSqrt(vec4 r){return 1.79284291400159 - 0.85373472095314 * r;}
    
    float snoise(vec3 v){
      const vec2  C = vec2(1.0/6.0, 1.0/3.0) ;
      const vec4  D = vec4(0.0, 0.5, 1.0, 2.0);
      vec3 i  = floor(v + dot(v, C.yyy) );
      vec3 x0 =   v - i + dot(i, C.xxx) ;
      vec3 g = step(x0.yzx, x0.xyz);
      vec3 l = 1.0 - g;
      vec3 i1 = min( g.xyz, l.zxy );
      vec3 i2 = max( g.xyz, l.zxy );
      vec3 x1 = x0 - i1 + 1.0 * C.xxx;
      vec3 x2 = x0 - i2 + 2.0 * C.xxx;
      vec3 x3 = x0 - 1.0 + 3.0 * C.xxx;
      vec4 p = permute( permute( permute( 
                 i.z + vec4(0.0, i1.z, i2.z, 1.0 ))
               + i.y + vec4(0.0, i1.y, i2.y, 1.0 )) 
               + i.x + vec4(0.0, i1.x, i2.x, 1.0 ));
      float n_ = 1.0/7.0;
      vec4  j = p - 49.0 * floor(p * n_ * n_);
      vec4 x_ = floor(j * n_);
      vec4 y_ = floor(j - 7.0 * x_ );
      vec4 x = x_ *n_ + n_/2.0;
      vec4 y = y_ *n_ + n_/2.0;
      vec4 h = 1.0 - abs(x) - abs(y);
      vec4 b0 = vec4( x.xy, y.xy );
      vec4 b1 = vec4( x.zw, y.zw );
      vec4 s0 = floor(b0)*2.0 + 1.0;
      vec4 s1 = floor(b1)*2.0 + 1.0;
      vec4 sh = -step(h, vec4(0.0));
      vec4 a0 = b0.xzyw + s0.xzyw*sh.xxyy ;
      vec4 a1 = b1.xzyw + s1.xzyw*sh.zzww ;
      vec3 p0 = vec3(a0.xy,h.x);
      vec3 p1 = vec3(a0.zw,h.y);
      vec3 p2 = vec3(a1.xy,h.z);
      vec3 p3 = vec3(a1.zw,h.w);
      vec4 norm = taylorInvSqrt(vec4(dot(p0,p0), dot(p1,p1), dot(p2, p2), dot(p3,p3)));
      p0 *= norm.x; p1 *= norm.y; p2 *= norm.z; p3 *= norm.w;
      vec4 m = max(0.6 - vec4(dot(x0,x0), dot(x1,x1), dot(x2,x2), dot(x3,x3)), 0.0);
      m = m * m;
      return 42.0 * dot( m*m, vec4( dot(p0,x0), dot(p1,x1), dot(p2,x2), dot(p3,x3) ) );
    }

    void main() {
        vec3 pos = texture2D(u_posTexture, vUv).xyz;
        vec3 target = texture2D(u_targetPos, vUv).xyz;
        
        float noiseFreq = 0.5;
        float noiseAmp = 0.01 + u_audio * 0.2;
        
        vec3 noisePos = vec3(pos.x * noiseFreq + u_time * 0.1, pos.y * noiseFreq, pos.z * noiseFreq);
        pos.x += snoise(noisePos) * noiseAmp;
        pos.y += snoise(noisePos + 1.0) * noiseAmp;
        pos.z += snoise(noisePos + 2.0) * noiseAmp;

        float dist = distance(pos.xy, u_mouse);
        if(dist < 0.5) {
            pos += normalize(pos - vec3(u_mouse, 0.0)) * (0.5 - dist) * 0.02;
        }

        pos = mix(pos, target, 0.05);
        
        if(u_explosion > 0.0) {
            pos += normalize(pos) * u_explosion * 0.5;
        }

        gl_FragColor = vec4(pos, 1.0);
    }
`;