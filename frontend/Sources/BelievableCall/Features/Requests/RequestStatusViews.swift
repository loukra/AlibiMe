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
            Text("\(request.channel == .call ? "Call" : "Text") scheduled in")
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
        case .call: return "We’ll call your verified number when the timer ends."
        case .text: return "We’ll text your verified number when the timer ends."
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
    /// See `Card`: lets the chip match the cards around it.
    var minHeight: CGFloat?
    @State private var now = Date()
    private let timer = Timer.publish(every: 1, on: .main, in: .common).autoconnect()

    public init(request: RequestSummary?, minHeight: CGFloat? = nil,
                onCancel: @escaping () -> Void, onOpen: @escaping () -> Void) {
        self.request = request
        self.minHeight = minHeight
        self.onCancel = onCancel
        self.onOpen = onOpen
    }

    public var body: some View {
        // The glass capsule (frame/background) is stable so nothing shifts; the
        // inner row is keyed by job id and push-transitions ("woosh") whenever
        // the displayed job changes — idle→job, job→next, job→idle. Same-job
        // ticks keep the same id, so they morph in place (no woosh).
        ZStack {
            row
                .id(request?.id ?? "idle")
                // Idle ⇄ job is a gentle fade; job ⇄ job (switch/delete-to-next)
                // is a clearly visible horizontal slide.
                .transition(rowTransition)
        }
        .frame(maxWidth: .infinity, minHeight: 44, alignment: .leading)
        .padding(Spacing.m)
        .reportsCardHeight(minHeight != nil)
        .frame(minHeight: minHeight)
        .fixedSize(horizontal: false, vertical: true)
        // Same glass, corners and shadow as `Card`, so it pairs with the
        // template card below it.
        .background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: Radius.card, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: Radius.card, style: .continuous)
                .strokeBorder(Theme.glassBorder, lineWidth: 1)
        )
        .clipShape(RoundedRectangle(cornerRadius: Radius.card, style: .continuous))
        .shadow(color: Theme.cardShadow, radius: 16, x: 0, y: 8)
        .animation(.spring(response: 0.38, dampingFraction: 0.74), value: request?.id)
        .onReceive(timer) { now = $0 }
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
        HStack(spacing: Spacing.m) {
            Button(action: onOpen) {
                HStack(spacing: Spacing.s) {
                    Image(systemName: leadingIcon)
                        .foregroundStyle(request == nil ? Color.secondary : Theme.accent)
                        .frame(width: 22)
                    VStack(alignment: .leading, spacing: 0) {
                        Text(captionText)
                            .font(.caption).foregroundStyle(.secondary)
                        Text(mainText)
                            .font(.headline.monospacedDigit())
                            .foregroundStyle(request == nil ? Color.secondary : Color.primary)
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
        return request.channel.systemImage
    }
    private var captionText: String {
        guard let request else { return "Upcoming" }
        return "Next \(request.channel == .call ? "call" : "text")"
    }
    private var mainText: String {
        guard let request else { return "Nothing scheduled" }
        let remaining = request.secondsRemaining(now: now)
        // Due or already handed to the provider: say what's happening instead
        // of a countdown frozen at 00:00.
        if remaining == 0 || request.status != .scheduled {
            return request.channel == .call ? "Calling you…" : "Texting you…"
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
