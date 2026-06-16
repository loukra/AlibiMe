import Foundation
import Observation

/// Chronological history across both channels, with pull-to-refresh and
/// pagination when the backend reports more pages.
@MainActor
@Observable
public final class HistoryViewModel {
    public private(set) var items: [HistoryEntry] = []
    public private(set) var isLoading = false
    public private(set) var isLoadingMore = false
    public private(set) var hasMore = false
    public var errorMessage: String?

    private let service: HistoryServicing
    private let requests: RequestServicing?
    private let pageSize: Int
    private var offset = 0
    public var onSessionExpired: (() -> Void)?

    public init(service: HistoryServicing, requests: RequestServicing? = nil, pageSize: Int = 20) {
        self.service = service
        self.requests = requests
        self.pageSize = pageSize
    }

    public var isEmpty: Bool { items.isEmpty && !isLoading }

    /// Pending (cancelable, not-yet-executed) jobs, soonest first.
    public var pendingItems: [HistoryEntry] {
        items.filter { $0.isPending }.sorted { $0.executeAt < $1.executeAt }
    }

    /// Everything that already ran (or was canceled), newest first.
    public var pastItems: [HistoryEntry] {
        items.filter { !$0.isPending }
    }

    /// Cancel a pending job, then drop it from the list (or reload on error).
    public func cancel(_ entry: HistoryEntry) async {
        guard let requests, entry.cancelable else { return }
        do {
            _ = try await requests.cancel(id: entry.id)
            items.removeAll { $0.id == entry.id }
        } catch {
            handle(error)
            await load()
        }
    }

    public func load() async {
        guard !isLoading else { return }  // avoid overlapping reloads (e.g. onAppear + pull)
        isLoading = true
        errorMessage = nil
        defer { isLoading = false }
        do {
            let page = try await service.list(limit: pageSize, offset: 0)
            items = page.items
            offset = page.nextOffset
            hasMore = page.hasMore
        } catch {
            handle(error)
        }
    }

    public func refresh() async { await load() }

    public func loadMore() async {
        guard hasMore, !isLoadingMore, !isLoading else { return }
        isLoadingMore = true
        defer { isLoadingMore = false }
        do {
            let page = try await service.list(limit: pageSize, offset: offset)
            items.append(contentsOf: page.items)
            offset = page.nextOffset
            hasMore = page.hasMore
        } catch {
            handle(error)
        }
    }

    private func handle(_ error: Error) {
        let apiError = asAPIError(error)
        if apiError.requiresReauth { onSessionExpired?(); return }
        errorMessage = ErrorCopy.userMessage(for: apiError)
    }
}
