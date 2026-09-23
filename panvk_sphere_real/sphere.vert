#version 450

layout(location = 0) in vec3 inPos;
layout(location = 1) in vec3 inNormal;
layout(location = 2) in float inFactor;

layout(push_constant) uniform PC {
    mat4 mvp;
    float time;
} pc;

layout(location = 0) out vec3 outColor;

void main() {
    // HUD verts: factor < 0, already in clip space. Color packed in normal.
    if (inFactor < 0.0) {
        gl_Position = vec4(inPos.xy, 0.0, 1.0);
        outColor = inNormal;
        return;
    }

    gl_Position = pc.mvp * vec4(inPos, 1.0);

    vec3 lightDir = normalize(vec3(0.6, 0.6, 0.5));
    float diff = max(dot(normalize(inNormal), lightDir), 0.0);
    float lighting = 0.25 + 0.75 * diff;

    const float twopi = 6.283185307;
    vec3 baseColor = vec3(
        abs(sin(pc.time + inFactor * twopi)),
        abs(cos(pc.time * 1.3 + inFactor * twopi)),
        abs(sin(pc.time * 0.7 + inFactor * twopi))
    );

    outColor = baseColor * lighting;
}
