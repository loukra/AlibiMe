#if canImport(SwiftUI)
import SwiftUI

/// Chronological history across both channels.
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
            .background(Theme.background.ignoresSafeArea())
            .navigationTitle("History")
            .task { if vm.items.isEmpty { await vm.load() } }
        }
    }

    private var list: some View {
        ScrollView {
            LazyVStack(spacing: Spacing.s) {
                if let error = vm.errorMessage {
                    ErrorBanner(error)
                }
                ForEach(vm.items) { item in
                    HistoryRow(item: item)
                        .onAppear {
                            if item.id == vm.items.last?.id { Task { await vm.loadMore() } }
                        }
                }
                if vm.isLoadingMore { ProgressView().padding() }
            }
            .padding(Spacing.m)
        }
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

struct HistoryRow: View {
    let item: HistoryEntry

    var body: some View {
        Card {
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
