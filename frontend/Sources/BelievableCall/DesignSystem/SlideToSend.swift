#if canImport(SwiftUI)
import SwiftUI

/// Slide-to-confirm for the send action, which costs credits: a stray tap
/// can't trigger it, only dragging the knob to the end. VoiceOver gets a plain
/// button action instead of the drag.
public struct SlideToSend: View {
    let title: String
    /// Second line under the title, e.g. "Slide to send · 1 credit".
    var subtitle: String?
    var systemImage: String
    var isLoading: Bool
    var isEnabled: Bool
    let action: () -> Void

    @State private var offset: CGFloat = 0
    private let knob: CGFloat = 56
    private let inset: CGFloat = 4
    /// How far along the track the knob must be on release to send.
    private let threshold: CGFloat = 0.85

    public init(_ title: String,
                subtitle: String? = nil,
                systemImage: String,
                isLoading: Bool = false,
                isEnabled: Bool = true,
                action: @escaping () -> Void) {
        self.title = title
        self.subtitle = subtitle
        self.systemImage = systemImage
        self.isLoading = isLoading
        self.isEnabled = isEnabled
        self.action = action
    }

    public var body: some View {
        GeometryReader { geo in
            let travel = max(geo.size.width - knob - inset * 2, 1)
            let progress = offset / travel
            ZStack(alignment: .leading) {
                VStack(spacing: 2) {
                    Text(title).fontWeight(.semibold)
                    if let subtitle {
                        Text(subtitle).font(.caption).opacity(0.85)
                    }
                }
                .foregroundStyle(.white)
                .lineLimit(1)
                .minimumScaleFactor(0.8)
                .frame(maxWidth: .infinity)
                .padding(.leading, knob)
                .padding(.trailing, Spacing.m)
                .opacity(1 - min(progress * 1.5, 1))

                Circle()
                    .fill(.white)
                    .frame(width: knob, height: knob)
                    .overlay {
                        if isLoading {
                            ProgressView().tint(Theme.accentFill)
                        } else {
                            Image(systemName: systemImage)
                                .font(.title3.weight(.semibold))
                                .foregroundStyle(Theme.accentFill)
                        }
                    }
                    .shadow(color: .black.opacity(0.15), radius: 4, x: 0, y: 2)
                    .offset(x: inset + offset)
                    .gesture(drag(travel: travel), including: isEnabled && !isLoading ? .all : .none)
            }
            .frame(width: geo.size.width, height: geo.size.height)
            .bcGlassTint(Theme.accentFill, in: Capsule())
            .shadow(color: Theme.accentFill.opacity(0.22), radius: 12, x: 0, y: 6)
        }
        .frame(height: knob + inset * 2)
        .opacity(isEnabled ? 1 : 0.5)
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(subtitle.map { "\(title), \($0)" } ?? title)
        .accessibilityAddTraits(.isButton)
        .accessibilityAction {
            if isEnabled && !isLoading { action() }
        }
    }

    private func drag(travel: CGFloat) -> some Gesture {
        DragGesture(minimumDistance: 0)
            .onChanged { value in
                offset = min(max(0, value.translation.width), travel)
            }
            .onEnded { _ in
                if offset >= travel * threshold {
                    offset = travel
                    Haptics.play(.impact)
                    action()
                    withAnimation(.spring(duration: 0.4).delay(0.5)) { offset = 0 }
                } else {
                    withAnimation(.spring(duration: 0.3)) { offset = 0 }
                }
            }
    }
}
#endif
