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
    private let pageSize: Int
    private var offset = 0
    public var onSessionExpired: (() -> Void)?

    public init(service: HistoryServicing, pageSize: Int = 20) {
        self.service = service
        self.pageSize = pageSize
    }

    public var isEmpty: Bool { items.isEmpty && !isLoading }

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
