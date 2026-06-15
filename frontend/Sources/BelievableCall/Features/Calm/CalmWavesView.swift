#if canImport(SwiftUI)
import SwiftUI

/// A deliberately empty, calming screen — nothing but slow, layered waves
/// drifting across the brand gradient. No data, no controls.
public struct CalmWavesView: View {
    public init() {}

    public var body: some View {
        ZStack {
            Theme.backgroundGradient.ignoresSafeArea()
            TimelineView(.animation) { timeline in
                let t = timeline.date.timeIntervalSinceReferenceDate
                Canvas { context, size in
                    // A few layered sine waves at different depths, speeds, and
                    // opacities for a gentle parallax.
                    let layers: [(amp: CGFloat, len: CGFloat, speed: Double, base: CGFloat, opacity: Double)] = [
                        (18, 0.9, 0.35, 0.62, 0.10),
                        (26, 1.2, 0.22, 0.72, 0.14),
                        (34, 1.5, 0.15, 0.82, 0.20),
                    ]
                    for layer in layers {
                        let phase = CGFloat(t * layer.speed)
                        let path = wave(
                            in: size,
                            amplitude: layer.amp,
                            wavelength: size.width * layer.len,
                            phase: phase,
                            baseline: size.height * layer.base
                        )
                        context.fill(path, with: .color(Theme.accent.opacity(layer.opacity)))
                    }
                }
                .ignoresSafeArea()
            }
        }
        .accessibilityLabel("Calm waves")
    }

    private func wave(
        in size: CGSize,
        amplitude: CGFloat,
        wavelength: CGFloat,
        phase: CGFloat,
        baseline: CGFloat
    ) -> Path {
        var path = Path()
        path.move(to: CGPoint(x: 0, y: size.height))
        path.addLine(to: CGPoint(x: 0, y: baseline))
        var x: CGFloat = 0
        let step: CGFloat = 4
        while x <= size.width {
            let y = baseline + sin((x / max(wavelength, 1)) * 2 * .pi + phase) * amplitude
            path.addLine(to: CGPoint(x: x, y: y))
            x += step
        }
        path.addLine(to: CGPoint(x: size.width, y: size.height))
        path.closeSubpath()
        return path
    }
}

struct CalmWavesView_Previews: PreviewProvider {
    static var previews: some View {
        CalmWavesView()
    }
}
#endif
