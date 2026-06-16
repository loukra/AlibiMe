#if canImport(SwiftUI)
import SwiftUI

/// History across both channels: a "Pending" section of upcoming jobs (with the
/// execution time and swipe-to-cancel) above the chronological past.
public struct HistoryView: View {
    @Bindable var vm: HistoryViewModel

    public init(vm: HistoryViewModel) { self.vm = vm }

    public var body: some View {
        NavigationStack {
            Group {
                if vm.isEmpty {
                    emptyState
                } else {
                    list
                }
            }
            .bcTabBarClearance()
            .bcScreenBackground()
            .navigationTitle("History")
            // Reload whenever the tab becomes visible (e.g. after scheduling on
            // Home), plus pull-to-refresh. Rows stay on screen during reload.
            .onAppear { Task { await vm.load() } }
        }
    }

    private var list: some View {
        List {
            if let error = vm.errorMessage {
                Section { ErrorBanner(error) }
            }
            if !vm.pendingItems.isEmpty {
                Section("Pending") {
                    ForEach(vm.pendingItems) { item in
                        PendingRow(item: item)
                            .swipeActions(edge: .trailing) {
                                if item.cancelable {
                                    Button(role: .destructive) {
                                        Task { await vm.cancel(item) }
                                    } label: { Label("Cancel", systemImage: "xmark") }
                                }
                            }
                    }
                }
            }
            if !vm.pastItems.isEmpty {
                Section(vm.pendingItems.isEmpty ? "" : "Recent") {
                    ForEach(vm.pastItems) { item in
                        HistoryRow(item: item)
                            .onAppear {
                                if item.id == vm.pastItems.last?.id { Task { await vm.loadMore() } }
                            }
                    }
                }
            }
            if vm.isLoadingMore {
                HStack { Spacer(); ProgressView(); Spacer() }
            }
        }
        .bcClearScrollBackground()
        .refreshable { await vm.refresh() }
    }

    private var emptyState: some View {
        VStack(spacing: Spacing.m) {
            Image(systemName: "clock.arrow.circlepath")
                .font(.system(size: 40))
                .foregroundStyle(.secondary)
            Text("No requests yet")
                .font(.headline)
            Text("Your calls and texts will appear here.")
                .font(.subheadline)
                .foregroundStyle(.secondary)
        }
        .padding(Spacing.xl)
    }
}

/// An upcoming job: channel, template, and a live countdown to execution.
struct PendingRow: View {
    let item: HistoryEntry
    @State private var now = Date()
    private let timer = Timer.publish(every: 1, on: .main, in: .common).autoconnect()

    var body: some View {
        HStack(spacing: Spacing.m) {
            Image(systemName: item.channel.systemImage)
                .font(.title3).foregroundStyle(Theme.accent).frame(width: 28)
            VStack(alignment: .leading, spacing: 2) {
                Text(item.templateLabel).font(.subheadline.weight(.medium))
                Text(item.executeAt, format: .dateTime.month().day().hour().minute())
                    .font(.caption).foregroundStyle(.secondary)
            }
            Spacer()
            Text(countdown)
                .font(.subheadline.weight(.semibold).monospacedDigit())
                .foregroundStyle(Theme.accent)
        }
        .onReceive(timer) { now = $0 }
        .accessibilityElement(children: .combine)
        .accessibilityHint("Swipe left to cancel")
    }

    private var countdown: String {
        let remaining = max(0, Int(item.executeAt.timeIntervalSince(now)))
        return String(format: "%02d:%02d", remaining / 60, remaining % 60)
    }
}

struct HistoryRow: View {
    let item: HistoryEntry

    var body: some View {
        HStack(spacing: Spacing.m) {
            Image(systemName: item.channel.systemImage)
                .font(.title3)
                .foregroundStyle(Theme.accent)
                .frame(width: 28)
            VStack(alignment: .leading, spacing: Spacing.xs) {
                Text(item.templateLabel)
                    .font(.subheadline.weight(.medium))
                Text(item.requestedAt, format: .dateTime.month().day().hour().minute())
                    .font(.caption)
                    .foregroundStyle(.secondary)
                if let preview = item.preview {
                    Text(preview)
                        .font(.footnote)
                        .foregroundStyle(.secondary)
                        .lineLimit(1)
                }
            }
            Spacer()
            VStack(alignment: .trailing, spacing: Spacing.xs) {
                StatusBadge(status: item.status, channel: item.channel)
                if let duration = item.durationSeconds {
                    Text("\(duration)s")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
            }
        }
        .accessibilityElement(children: .combine)
    }
}

struct HistoryView_Previews: PreviewProvider {
    static var previews: some View {
        HistoryView(vm: HistoryViewModel(service: MockHistoryService()))
    }
}
#endif
