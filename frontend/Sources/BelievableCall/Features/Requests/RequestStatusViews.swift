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

/// Compact "next job" chip shown on Home above the composer. Shows a live
/// countdown to the soonest upcoming job with a cancel button; tapping the chip
/// body (not the ✕) opens History to see all pending jobs.
public struct NextJobChip: View {
    let request: RequestSummary
    let onCancel: () -> Void
    let onOpen: () -> Void
    @State private var now = Date()
    private let timer = Timer.publish(every: 1, on: .main, in: .common).autoconnect()

    public init(request: RequestSummary, onCancel: @escaping () -> Void, onOpen: @escaping () -> Void) {
        self.request = request
        self.onCancel = onCancel
        self.onOpen = onOpen
    }

    public var body: some View {
        HStack(spacing: Spacing.m) {
            Button(action: onOpen) {
                HStack(spacing: Spacing.s) {
                    Image(systemName: request.channel.systemImage)
                        .foregroundStyle(Theme.accent)
                    VStack(alignment: .leading, spacing: 0) {
                        Text("Next \(request.channel == .call ? "call" : "text")")
                            .font(.caption).foregroundStyle(.secondary)
                        Text(countdown)
                            .font(.headline.monospacedDigit())
                    }
                    Spacer(minLength: 0)
                    Image(systemName: "chevron.right").font(.caption).foregroundStyle(.secondary)
                }
                .contentShape(Rectangle())
            }
            .buttonStyle(.plain)

            if request.cancelable {
                Button(action: onCancel) {
                    Image(systemName: "xmark.circle.fill")
                        .font(.title2)
                        .foregroundStyle(.secondary)
                }
                .buttonStyle(.plain)
                .accessibilityLabel("Cancel next job")
            }
        }
        .padding(Spacing.m)
        .background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: Radius.control, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: Radius.control, style: .continuous)
                .strokeBorder(Theme.glassBorder, lineWidth: 1)
        )
        .onReceive(timer) { now = $0 }
        .accessibilityHint("Opens History to see all pending jobs")
    }

    private var countdown: String {
        let remaining = request.secondsRemaining(now: now)
        return String(format: "%02d:%02d", remaining / 60, remaining % 60)
    }
}
#endif
