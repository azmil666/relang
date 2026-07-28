/**
 * Donut.js - 3D ASCII Donut Renderer
 * Faithful Node.js port of source/donut.py
 */

function calculateSin(x) {
    return Math.sin(x);
}

function calculateCos(x) {
    return Math.cos(x);
}

function drawDonut() {
    let angle1 = 0.0;
    let angle2 = 0.0;
    let zBuffer = new Float64Array(1760);
    let pixels = new Array(1760).fill(' ');

    // Clear the console initially (ANSI escape sequence)
    process.stdout.write('\x1b[2J');

    const renderFrame = () => {
        // Clear pixel and z_buffer lists for the current frame
        pixels.fill(' ');
        zBuffer.fill(0.0);

        // Calculate position and brightness of each pixel
        for (let j = 0; j < 628; j += 7) {
            for (let i = 0; i < 628; i += 2) {
                const sinI = calculateSin(i / 100.0);
                const cosJ = calculateCos(j / 100.0);
                const sinAngle1 = calculateSin(angle1);
                const sinJ = calculateSin(j / 100.0);
                const cosAngle1 = calculateCos(angle1);
                
                const height = cosJ + 2;
                const distance = 1 / (sinI * height * sinAngle1 + sinJ * cosAngle1 + 5);
                
                const cosI = calculateCos(i / 100.0);
                const cosAngle2 = calculateCos(angle2);
                const sinAngle2 = calculateSin(angle2);
                
                const sinHeight = sinI * height * cosAngle1 - sinJ * sinAngle1;
                
                const x = Math.floor(40 + 30 * distance * (cosI * height * cosAngle2 - sinHeight * sinAngle2));
                const y = Math.floor(12 + 15 * distance * (cosI * height * sinAngle2 + sinHeight * cosAngle2));
                
                const index = x + 80 * y;
                
                const brightness = Math.floor(
                    8 * (
                        (sinJ * sinAngle1 - sinI * cosJ * cosAngle1) * cosAngle2 -
                        sinI * cosJ * sinAngle1 -
                        sinJ * cosAngle1 -
                        cosI * cosJ * sinAngle2
                    )
                );

                if (y >= 0 && y < 22 && x >= 0 && x < 80 && distance > zBuffer[index]) {
                    zBuffer[index] = distance;
                    const charIndex = brightness > 0 ? brightness : 0;
                    const shadingChars = '.,-~:;=!*#$@';
                    pixels[index] = shadingChars[charIndex] || shadingChars[0];
                }
            }
        }

        // Move cursor to top-left position and output current frame
        process.stdout.write('\x1b[H');
        process.stdout.write(pixels.join(''));

        // Update rotation angles for the next frame
        angle1 += 0.30;
        angle2 += 0.15;

        // Schedule next frame (~30 FPS)
        setImmediate(renderFrame);
    };

    renderFrame();
}

function main() {
    drawDonut();
}

main();