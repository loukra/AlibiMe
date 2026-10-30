#if canImport(SwiftUI)
import SwiftUI

/// A translucent, softly elevated "glass" card surface.
public struct Card<Content: View>: View {
    private let content: Content
    private let minHeight: CGFloat?
    /// `minHeight` (padding included) lets cards that sit together share one
    /// height: such a card reports its natural height (`CardHeightKey`), the
    /// screen passes the tallest back in, and the content is centered in it.
    public init(minHeight: CGFloat? = nil, @ViewBuilder content: () -> Content) {
        self.content = content()
        self.minHeight = minHeight
    }
    public var body: some View {
        content
            .padding(Spacing.m)
            .reportsCardHeight(minHeight != nil)
            .frame(maxWidth: .infinity, minHeight: minHeight, alignment: .leading)
            .fixedSize(horizontal: false, vertical: true)
            .background(
                .ultraThinMaterial,
                in: RoundedRectangle(cornerRadius: Radius.card, style: .continuous)
            )
            .overlay(
                RoundedRectangle(cornerRadius: Radius.card, style: .continuous)
                    .strokeBorder(Theme.glassBorder, lineWidth: 1)
            )
            .shadow(color: Theme.cardShadow, radius: 16, x: 0, y: 8)
    }
}

/// The tallest natural height among cards that share one (see `Card`).
public struct CardHeightKey: PreferenceKey {
    public static let defaultValue: CGFloat = 0
    public static func reduce(value: inout CGFloat, nextValue: () -> CGFloat) {
        value = max(value, nextValue())
    }
}

extension View {
    /// Measured before the shared minimum is applied, so a card never reports
    /// back the height it was given.
    @ViewBuilder func reportsCardHeight(_ enabled: Bool = true) -> some View {
        if enabled {
            background(GeometryReader { proxy in
                Color.clear.preference(key: CardHeightKey.self, value: proxy.size.height)
            })
        } else {
            self
        }
    }
}

/// The large home CTA. Adapts color to enabled/destructive state.
public struct PrimaryButton: View {
    let title: String
    var systemImage: String?
    var isLoading: Bool
    var role: Role
    let action: () -> Void

    public enum Role { case primary, destructive }

    public init(_ title: String,
                systemImage: String? = nil,
                isLoading: Bool = false,
                role: Role = .primary,
                action: @escaping () -> Void) {
        self.title = title
        self.systemImage = systemImage
        self.isLoading = isLoading
        self.role = role
        self.action = action
    }

    public var body: some View {
        Button(action: action) {
            HStack(spacing: Spacing.s) {
                if isLoading {
                    ProgressView().tint(.white)
                } else if let systemImage {
                    Image(systemName: systemImage)
                }
                Text(title).fontWeight(.semibold)
            }
            .frame(maxWidth: .infinity)
            .frame(minHeight: 30)
            .padding(.vertical, Spacing.m)
            .foregroundStyle(.white)
            .bcGlassTint(
                role == .destructive ? Theme.destructive : Theme.accent,
                in: RoundedRectangle(cornerRadius: Radius.control, style: .continuous),
                interactive: true
            )
            .shadow(
                color: (role == .destructive ? Theme.destructive : Theme.accent).opacity(0.22),
                radius: 12, x: 0, y: 6
            )
        }
        .buttonStyle(.plain)
        .disabled(isLoading)
    }
}

/// A selectable pill (used for channel + timing presets).
public struct SelectablePill: View {
    let title: String
    var systemImage: String?
    let isSelected: Bool
    let action: () -> Void

    public init(_ title: String, systemImage: String? = nil, isSelected: Bool, action: @escaping () -> Void) {
        self.title = title
        self.systemImage = systemImage
        self.isSelected = isSelected
        self.action = action
    }

    public var body: some View {
        Button(action: action) {
            HStack(spacing: Spacing.xs) {
                if let systemImage { Image(systemName: systemImage) }
                Text(title)
            }
            .font(.subheadline.weight(.medium))
            .padding(.horizontal, Spacing.m)
            .padding(.vertical, Spacing.s)
            .frame(maxWidth: .infinity)
            .foregroundStyle(isSelected ? Color.white : Color.primary)
            .background(
                isSelected ? AnyShapeStyle(Theme.accent) : AnyShapeStyle(Material.ultraThin),
                in: RoundedRectangle(cornerRadius: Radius.control, style: .continuous)
            )
            .overlay(
                RoundedRectangle(cornerRadius: Radius.control, style: .continuous)
                    .strokeBorder(isSelected ? Color.clear : Theme.glassBorder, lineWidth: 1)
            )
            .shadow(color: isSelected ? Theme.accent.opacity(0.25) : .clear, radius: 8, x: 0, y: 4)
        }
        .buttonStyle(.plain)
    }
}

/// One choice in a `SegmentedSelector`.
public struct SegmentItem: Identifiable, Equatable, Sendable {
    public let id: String
    public let title: String
    public init(id: String, title: String) {
        self.id = id
        self.title = title
    }
}

/// A sliding segmented control — the selected segment is a brand-accent capsule
/// that glides between options (à la the iOS camera mode switch). Selection is
/// reported via `onSelect`, so callers can drive a value *or* an action (e.g.
/// "Schedule" opening a sheet).
public struct SegmentedSelector: View {
    let items: [SegmentItem]
    let selectedID: String
    let onSelect: (String) -> Void
    @Namespace private var ns

    public init(items: [SegmentItem], selectedID: String, onSelect: @escaping (String) -> Void) {
        self.items = items
        self.selectedID = selectedID
        self.onSelect = onSelect
    }

    public var body: some View {
        HStack(spacing: 0) {
            ForEach(items) { item in
                let isSelected = item.id == selectedID
                Button {
                    Haptics.play(.impact)
                    onSelect(item.id)
                } label: {
                    Text(item.title)
                        .font(.subheadline.weight(.semibold))
                        .lineLimit(1)
                        .minimumScaleFactor(0.8)
                        .foregroundStyle(isSelected ? Color.white : Color.secondary)
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, Spacing.s)
                        .background {
                            if isSelected {
                                Color.clear
                                    .bcGlassTintCapsule(Theme.accent)
                                    .matchedGeometryEffect(id: "segmentedSelection", in: ns)
                            }
                        }
                        .contentShape(Capsule())
                }
                .buttonStyle(.plain)
                .accessibilityLabel(item.title)
                .accessibilityAddTraits(isSelected ? [.isButton, .isSelected] : .isButton)
            }
        }
        .padding(4)
        .bcGlassCapsule()
        .animation(.spring(response: 0.32, dampingFraction: 0.82), value: selectedID)
    }
}

/// Section header in the calm, serious tone.
public struct SectionHeader: View {
    let title: String
    public init(_ title: String) { self.title = title }
    public var body: some View {
        Text(title.uppercased())
            .font(.caption.weight(.semibold))
            .foregroundStyle(.secondary)
            .accessibilityAddTraits(.isHeader)
    }
}

/// Status chip that never relies on color alone (icon + text).
public struct StatusBadge: View {
    let status: RequestStatus
    let channel: Channel
    public init(status: RequestStatus, channel: Channel) {
        self.status = status
        self.channel = channel
    }
    public var body: some View {
        HStack(spacing: Spacing.xs) {
            Image(systemName: icon)
            Text(status.displayText(for: channel))
                .lineLimit(1)
        }
        .font(.subheadline.weight(.medium))
        .fixedSize()
        .padding(.horizontal, Spacing.s)
        .padding(.vertical, Spacing.xs)
        .foregroundStyle(tint)
        .background(tint.opacity(0.12))
        .clipShape(Capsule())
        .accessibilityElement(children: .combine)
    }

    private var tint: Color {
        switch status {
        case .completed: return Theme.success
        case .failed, .expired: return Theme.destructive
        case .noAnswer, .canceled: return .secondary
        default: return Theme.accent
        }
    }
    private var icon: String {
        switch status {
        case .completed: return "checkmark.circle.fill"
        case .failed, .expired: return "exclamationmark.triangle.fill"
        case .noAnswer: return "phone.down.fill"
        case .canceled: return "xmark.circle.fill"
        case .active, .providerAccepted: return "waveform"
        default: return "clock.fill"
        }
    }
}

/// Inline error banner with calm copy.
public struct ErrorBanner: View {
    let message: String
    public init(_ message: String) { self.message = message }
    public var body: some View {
        HStack(alignment: .top, spacing: Spacing.s) {
            Image(systemName: "exclamationmark.circle.fill")
            Text(message).font(.subheadline)
                .fixedSize(horizontal: false, vertical: true)
            Spacer(minLength: 0)
        }
        .foregroundStyle(Theme.destructive)
        .padding(Spacing.m)
        .background(Theme.destructive.opacity(0.10))
        .clipShape(RoundedRectangle(cornerRadius: Radius.control, style: .continuous))
        .accessibilityElement(children: .combine)
    }
}
#endif
