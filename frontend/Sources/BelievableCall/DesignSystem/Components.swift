#if canImport(SwiftUI)
import SwiftUI

/// A slightly elevated, rounded card surface.
public struct Card<Content: View>: View {
    private let content: Content
    public init(@ViewBuilder content: () -> Content) { self.content = content() }
    public var body: some View {
        content
            .padding(Spacing.m)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(Theme.card)
            .clipShape(RoundedRectangle(cornerRadius: Radius.card, style: .continuous))
            .overlay(
                RoundedRectangle(cornerRadius: Radius.card, style: .continuous)
                    .strokeBorder(Theme.subtleBorder, lineWidth: 1)
            )
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
            .background(role == .destructive ? Theme.destructive : Theme.accent)
            .clipShape(RoundedRectangle(cornerRadius: Radius.control, style: .continuous))
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
            .background(isSelected ? Theme.accent : Theme.card)
            .clipShape(RoundedRectangle(cornerRadius: Radius.control, style: .continuous))
            .overlay(
                RoundedRectangle(cornerRadius: Radius.control, style: .continuous)
                    .strokeBorder(isSelected ? Color.clear : Theme.subtleBorder, lineWidth: 1)
            )
        }
        .buttonStyle(.plain)
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
        }
        .font(.subheadline.weight(.medium))
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
        case .canceled: return .secondary
        default: return Theme.accent
        }
    }
    private var icon: String {
        switch status {
        case .completed: return "checkmark.circle.fill"
        case .failed, .expired: return "exclamationmark.triangle.fill"
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
