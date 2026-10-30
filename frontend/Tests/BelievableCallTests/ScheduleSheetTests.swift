import XCTest
@testable import BelievableCall

final class ScheduleSheetTests: XCTestCase {
    private var calendar: Calendar = {
        var c = Calendar(identifier: .gregorian)
        c.timeZone = TimeZone(identifier: "Europe/Berlin")!
        return c
    }()

    private func date(_ day: Int, _ hour: Int, _ minute: Int) -> Date {
        calendar.date(from: DateComponents(year: 2026, month: 10, day: day, hour: hour, minute: minute))!
    }

    func testATimeStillAheadIsToday() {
        let now = date(30, 17, 0)
        XCTAssertEqual(ScheduleSheet.nextOccurrence(of: date(1, 18, 30), after: now, calendar: calendar),
                       date(30, 18, 30))
    }

    func testATimeAlreadyPassedIsTomorrow() {
        let now = date(30, 17, 0)
        XCTAssertEqual(ScheduleSheet.nextOccurrence(of: date(1, 7, 0), after: now, calendar: calendar),
                       date(31, 7, 0))
    }

    func testTheCurrentMinuteIsTomorrowBecauseOfTheLeadTime() {
        let now = date(30, 17, 0)
        XCTAssertEqual(ScheduleSheet.nextOccurrence(of: date(1, 17, 0), after: now, calendar: calendar),
                       date(31, 17, 0))
    }

    func testNeverBeyondTheDayWindow() {
        let now = date(30, 17, 0).addingTimeInterval(30)
        let picked = ScheduleSheet.nextOccurrence(of: date(1, 17, 1), after: now, calendar: calendar)
        XCTAssertLessThanOrEqual(picked.timeIntervalSince(now), 24 * 3600)
    }

    func testDescribeSaysTodayOrTomorrow() {
        let now = date(30, 17, 0)
        XCTAssertTrue(ScheduleSheet.describe(date(30, 18, 30), now: now, calendar: calendar)
            .hasPrefix("today at "))
        XCTAssertTrue(ScheduleSheet.describe(date(31, 7, 0), now: now, calendar: calendar)
            .hasPrefix("tomorrow at "))
    }

    func testQuickPickTitles() {
        XCTAssertEqual(ScheduleSheet.title(15), "In 15 min")
        XCTAssertEqual(ScheduleSheet.title(120), "In 2 h")
    }
}
