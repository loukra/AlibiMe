#if canImport(SwiftUI)
import SwiftUI

/// Status-first card shown on Home when a live request exists. Makes clear the
/// app has accepted the request, with a countdown and cancel when allowed.
public struct ActiveRequestCard: View {
    let request: RequestSummary
    let onCancel: () -> Void
    let onRefresh: () -> Void
    @State private var now = Date()
    private let timer = Timer.publish(every: 1, on: .main, in: .common).autoconnect()

    public init(request: RequestSummary, onCancel: @escaping () -> Void, onRefresh: @escaping () -> Void) {
        self.request = request
        self.onCancel = onCancel
        self.onRefresh = onRefresh
    }

    public var body: some View {
        Card {
            VStack(alignment: .leading, spacing: Spacing.m) {
                HStack {
                    StatusBadge(status: request.status, channel: request.channel)
                    Spacer()
                    Image(systemName: request.channel.systemImage).foregroundStyle(.secondary)
                }
                if request.status == .scheduled {
                    countdown
                }
                Text(summaryLine)
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
                if request.cancelable {
                    PrimaryButton("Cancel request", systemImage: "xmark", role: .destructive) {
                        Haptics.play(.warning)
                        onCancel()
                    }
                }
            }
        }
        .onReceive(timer) { value in
            now = value
            // Poll backend occasionally for status while the request is live.
            if Int(value.timeIntervalSinceReferenceDate) % 5 == 0 { onRefresh() }
        }
    }

    private var countdown: some View {
        let remaining = request.secondsRemaining(now: now)
        let minutes = remaining / 60
        let seconds = remaining % 60
        return VStack(alignment: .leading, spacing: Spacing.xs) {
            Text(request.channel == .call ? "Call scheduled in" : "Text scheduled in")
                .font(.subheadline)
                .foregroundStyle(.secondary)
            Text(String(format: "%02d:%02d", minutes, seconds))
                .font(.system(size: 40, weight: .semibold, design: .monospaced))
                .monospacedDigit()
                .accessibilityLabel("\(minutes) minutes \(seconds) seconds remaining")
        }
    }

    private var summaryLine: String {
        switch request.channel {
        case .call: return String(localized: "We’ll call your verified number when the timer ends.")
        case .text: return String(localized: "We’ll text your verified number when the timer ends.")
        }
    }
}

/// Always-present "next job" control on Home. Shows a live countdown to the
/// soonest upcoming job (with a cancel button), or a calm idle state when there
/// is none. Tapping the body opens History. Its height is identical in both
/// states so the Home layout never shifts.
public struct NextJobChip: View {
    let request: RequestSummary?
    let onCancel: () -> Void
    let onOpen: () -> Void
    @State private var now = Date()
    @State private var pulsing = false
    private let timer = Timer.publish(every: 1, on: .main, in: .common).autoconnect()

    public init(request: RequestSummary?,
                onCancel: @escaping () -> Void, onOpen: @escaping () -> Void) {
        self.request = request
        self.onCancel = onCancel
        self.onOpen = onOpen
    }

    public var body: some View {
        // The frame and background are stable so nothing shifts; the inner row
        // is keyed by job id and push-transitions ("woosh") whenever the
        // displayed job changes. Same-job ticks keep the id and morph in place.
        ZStack {
            row
                .id(request?.id ?? "idle")
                .transition(rowTransition)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(Spacing.m)
        // Tinted, not the white glass of the cards below: this is something
        // already running, not part of the form for a new alibi.
        .background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: Radius.card, style: .continuous))
        .background(Theme.accent.opacity(0.16), in: RoundedRectangle(cornerRadius: Radius.card, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: Radius.card, style: .continuous)
                .fill(Theme.accent.opacity(0.10))
                // Tint only: taps go through to the row and the cancel button.
                .allowsHitTesting(false)
        )
        .overlay(
            RoundedRectangle(cornerRadius: Radius.card, style: .continuous)
                .strokeBorder(Theme.accent.opacity(0.45), lineWidth: 1.5)
        )
        .clipShape(RoundedRectangle(cornerRadius: Radius.card, style: .continuous))
        .shadow(color: Theme.cardShadow, radius: 16, x: 0, y: 8)
        .animation(.spring(response: 0.38, dampingFraction: 0.74), value: request?.id)
        .onReceive(timer) { now = $0 }
        .onAppear { pulsing = true }
        .accessibilityHint(request == nil ? "Opens History" : "Opens History to see all pending jobs")
    }

    /// Gentle fade when the idle state is involved; a visible slide for a
    /// job→job swap so switching/deleting clearly reads as a different timer.
    private var rowTransition: AnyTransition {
        request == nil
            ? .opacity
            : .asymmetric(
                insertion: .move(edge: .trailing).combined(with: .opacity),
                removal: .move(edge: .leading).combined(with: .opacity)
            )
    }

    private var row: some View {
        HStack(alignment: .center, spacing: Spacing.m) {
            Button(action: onOpen) {
                HStack(spacing: Spacing.m) {
                    ZStack {
                        Circle().fill(Theme.accentFill)
                        Image(systemName: leadingIcon)
                            .font(.body.weight(.semibold))
                            .foregroundStyle(.white)
                    }
                    .frame(width: 44, height: 44)
                    .opacity(request == nil ? 0.5 : 1)
                    VStack(alignment: .leading, spacing: 2) {
                        HStack(spacing: Spacing.xs + 2) {
                            if request != nil {
                                Circle()
                                    .fill(Theme.accent)
                                    .frame(width: 7, height: 7)
                                    .opacity(pulsing ? 0.25 : 1)
                                    .animation(.easeInOut(duration: 0.9).repeatForever(autoreverses: true), value: pulsing)
                                    .accessibilityHidden(true)
                            }
                            Text(captionText)
                                .font(.subheadline.weight(.medium))
                                .foregroundStyle(.primary)
                                .lineLimit(2)
                        }
                        Text(mainText)
                            .font(.title.weight(.bold).monospacedDigit())
                            .foregroundStyle(request == nil ? Color.secondary : Theme.accent)
                            .lineLimit(1)
                            .minimumScaleFactor(0.6)
                            // Same-job countdown ticks morph rather than woosh.
                            .contentTransition(.numericText())
                    }
                    Spacer(minLength: 0)
                    Image(systemName: "chevron.right").font(.caption).foregroundStyle(.secondary)
                }
                .contentShape(Rectangle())
            }
            .buttonStyle(.plain)

            if request?.cancelable == true {
                Button(action: onCancel) {
                    Image(systemName: "xmark.circle.fill")
                        .font(.title2)
                        .foregroundStyle(.secondary)
                }
                .buttonStyle(.plain)
                .accessibilityLabel("Cancel next job")
            }
        }
    }

    private var leadingIcon: String {
        guard let request else { return "moon.stars" }
        return request.channel.outlineSymbol
    }
    /// Who and when, so it is clear this one is already on its way.
    private var captionText: String {
        guard let request else { return String(localized: "Upcoming") }
        let time = ScheduleSheet.clockTime(request.executeAt)
        if let name = request.senderIdentity?.displayName {
            return request.channel == .call ? String(localized: "\(name) calls you at \(time)")
                : String(localized: "\(name) texts you at \(time)")
        }
        return request.channel == .call ? String(localized: "Next call at \(time)")
            : String(localized: "Next text at \(time)")
    }
    private var mainText: String {
        guard let request else { return String(localized: "Nothing scheduled") }
        let remaining = request.secondsRemaining(now: now)
        // Due or already handed to the provider: say what's happening instead
        // of a countdown frozen at 00:00.
        if remaining == 0 || request.status != .scheduled {
            return request.channel == .call ? String(localized: "Calling you…") : String(localized: "Texting you…")
        }
        return Self.countdown(remaining)
    }

    /// "04:59", or "1:59:59" once it's an hour or more away.
    static func countdown(_ seconds: Int) -> String {
        if seconds >= 3600 {
            return String(format: "%d:%02d:%02d", seconds / 3600, seconds / 60 % 60, seconds % 60)
        }
        return String(format: "%02d:%02d", seconds / 60, seconds % 60)
    }
}
#endif
