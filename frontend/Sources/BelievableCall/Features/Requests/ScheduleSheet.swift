#if canImport(SwiftUI)
import SwiftUI

/// Picks when a call or text comes, within the next 24 hours: four quick picks,
/// or an exact time on a wheel. A time that has already passed today means
/// tomorrow, so the wheel never needs a date.
public struct ScheduleSheet: View {
    let timezone: String
    let onConfirm: (Date) -> Void
    let onCancel: () -> Void
    @State private var choice: Choice = .inMinutes(30)
    @State private var wheelTime: Date

    enum Choice: Equatable {
        case inMinutes(Int)
        case at
    }

    static let quickPicks = [15, 30, 60, 120]

    public init(timezone: String,
                onConfirm: @escaping (Date) -> Void,
                onCancel: @escaping () -> Void) {
        self.timezone = timezone
        self.onConfirm = onConfirm
        self.onCancel = onCancel
        _wheelTime = State(initialValue: Date().addingTimeInterval(3600))
    }

    public var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: Spacing.l) {
                    VStack(alignment: .leading, spacing: Spacing.s) {
                        SectionHeader("Quick pick")
                        LazyVGrid(columns: [GridItem(.flexible(), spacing: Spacing.s),
                                            GridItem(.flexible(), spacing: Spacing.s)],
                                  spacing: Spacing.s) {
                            ForEach(Self.quickPicks, id: \.self) { minutes in
                                quickPick(minutes)
                            }
                        }
                    }

                    VStack(alignment: .leading, spacing: Spacing.s) {
                        SectionHeader("Or at a time")
                        Card {
                            DatePicker("Time", selection: $wheelTime,
                                       displayedComponents: .hourAndMinute)
                                .bcWheelStyle()
                                .labelsHidden()
                                .frame(maxWidth: .infinity)
                                .onChange(of: wheelTime) { choice = .at }
                        }
                        .overlay(
                            RoundedRectangle(cornerRadius: Radius.card, style: .continuous)
                                .strokeBorder(choice == .at ? Theme.accent : Color.clear, lineWidth: 2)
                        )
                        Label("Times shown in \(timezone)", systemImage: "globe")
                            .font(.footnote)
                            .foregroundStyle(.secondary)
                    }
                }
                .padding(Spacing.m)
            }
            .safeAreaInset(edge: .bottom) {
                PrimaryButton("Schedule \(Self.describe(resolvedDate))", systemImage: "calendar") {
                    onConfirm(resolvedDate)
                }
                .padding(.horizontal, Spacing.m)
                .padding(.bottom, Spacing.s)
            }
            .bcScreenBackground()
            .navigationTitle("Schedule")
            .bcInlineNavTitle()
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel", action: onCancel)
                }
            }
        }
    }

    private func quickPick(_ minutes: Int) -> some View {
        let selected = choice == .inMinutes(minutes)
        return Button {
            choice = .inMinutes(minutes)
            Haptics.play(.impact)
        } label: {
            VStack(alignment: .leading, spacing: 2) {
                Text(Self.title(minutes))
                    .font(.subheadline.weight(.semibold))
                Text(Self.clockTime(Date().addingTimeInterval(TimeInterval(minutes * 60))))
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(Spacing.m)
            .background(.ultraThinMaterial,
                        in: RoundedRectangle(cornerRadius: Radius.control, style: .continuous))
            .overlay(
                RoundedRectangle(cornerRadius: Radius.control, style: .continuous)
                    .strokeBorder(selected ? Theme.accent : Theme.glassBorder,
                                  lineWidth: selected ? 2 : 1)
            )
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .accessibilityAddTraits(selected ? [.isButton, .isSelected] : .isButton)
    }

    private var resolvedDate: Date {
        switch choice {
        case .inMinutes(let minutes): return Date().addingTimeInterval(TimeInterval(minutes * 60))
        case .at: return Self.nextOccurrence(of: wheelTime, after: Date())
        }
    }
}

extension ScheduleSheet {
    static func title(_ minutes: Int) -> String {
        minutes < 60 ? String(localized: "In \(minutes) min") : String(localized: "In \(minutes / 60) h")
    }

    /// The wheel's hour and minute, today if still ahead (by more than a
    /// minute, the backend's lead time), otherwise tomorrow, never beyond 24 hours.
    static func nextOccurrence(of time: Date, after now: Date,
                               calendar: Calendar = .current) -> Date {
        let parts = calendar.dateComponents([.hour, .minute], from: time)
        let today = calendar.date(bySettingHour: parts.hour ?? 0, minute: parts.minute ?? 0,
                                  second: 0, of: now) ?? now
        if today > now.addingTimeInterval(60) { return today }
        let tomorrow = calendar.date(byAdding: .day, value: 1, to: today) ?? today
        // A time inside the next minute would land just past the 24-hour window.
        return min(tomorrow, now.addingTimeInterval(24 * 3600))
    }

    /// "today at 18:30" or "tomorrow at 07:00".
    static func describe(_ date: Date, now: Date = Date(), calendar: Calendar = .current) -> String {
        let time = clockTime(date)
        return calendar.isDate(date, inSameDayAs: now)
            ? String(localized: "today at \(time)") : String(localized: "tomorrow at \(time)")
    }

    static func clockTime(_ date: Date) -> String {
        date.formatted(date: .omitted, time: .shortened)
    }
}

private extension View {
    /// The wheel on iOS; the macOS test host has no wheel style.
    @ViewBuilder func bcWheelStyle() -> some View {
        #if os(iOS)
        datePickerStyle(.wheel)
        #else
        self
        #endif
    }
}

struct ScheduleSheet_Previews: PreviewProvider {
    static var previews: some View {
        ScheduleSheet(timezone: "Europe/Berlin", onConfirm: { _ in }, onCancel: {})
    }
}
#endif
