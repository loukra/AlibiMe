import XCTest
@testable import BelievableCall

@MainActor
final class PendingJobsHistoryTests: XCTestCase {
    private func entry(_ id: String, status: RequestStatus, cancelable: Bool, secs: TimeInterval) -> HistoryEntry {
        HistoryEntry(id: id, channel: .call, templateLabel: "Boss",
                     requestedAt: Date(), executeAt: Date().addingTimeInterval(secs),
                     status: status, cancelable: cancelable, durationSeconds: nil, preview: nil)
    }

    func testSplitsPendingFromPast() async {
        let history = MockHistoryService(items: [
            entry("p2", status: .scheduled, cancelable: true, secs: 300),
            entry("p1", status: .scheduled, cancelable: true, secs: 60),
            entry("done", status: .completed, cancelable: false, secs: -100),
        ])
        let vm = HistoryViewModel(service: history, requests: MockRequestService())
        await vm.load()
        // Pending sorted soonest-first; past separate.
        XCTAssertEqual(vm.pendingItems.map(\.id), ["p1", "p2"])
        XCTAssertEqual(vm.pastItems.map(\.id), ["done"])
    }

    func testCancelRemovesPendingJob() async {
        let history = MockHistoryService(items: [
            entry("p1", status: .scheduled, cancelable: true, secs: 60),
        ])
        let requests = MockRequestService()
        let vm = HistoryViewModel(service: history, requests: requests)
        await vm.load()
        await vm.cancel(vm.pendingItems[0])
        XCTAssertTrue(vm.pendingItems.isEmpty)
        XCTAssertEqual(requests.canceledIDs, ["p1"])
    }
}
