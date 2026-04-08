import java.time.LocalDate;
import java.time.temporal.ChronoUnit;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.HashMap;

/**
 * Red Moon Recovery - Cycle Engine (Java)
 * Handles cycle phase calculation, period prediction,
 * and environmental adjustment logic.
 * Called from Python via subprocess and returns JSON.
 */
public class CycleEngine {

    // Phase boundaries (cycle days)
    static final int MENSTRUAL_END   = 5;
    static final int FOLLICULAR_END  = 13;
    static final int OVULATORY_END   = 17;
    // Luteal is day 18 to end of cycle

    public static String getPhase(int cycleDay) {
        if (cycleDay <= MENSTRUAL_END)  return "menstrual";
        if (cycleDay <= FOLLICULAR_END) return "follicular";
        if (cycleDay <= OVULATORY_END)  return "ovulatory";
        return "luteal";
    }

    public static String getPhaseEmoji(String phase) {
        switch (phase) {
            case "menstrual":  return "Menstrual";
            case "follicular": return "Follicular";
            case "ovulatory":  return "Ovulatory";
            case "luteal":     return "Luteal";
            default:           return "Unknown";
        }
    }

    public static int getCycleDay(String lastPeriodStr, int cycleLength) {
        try {
            LocalDate lastPeriod = LocalDate.parse(lastPeriodStr);
            LocalDate today = LocalDate.now();
            long daysSince = ChronoUnit.DAYS.between(lastPeriod, today);
            int cycleDay = (int)(daysSince % cycleLength) + 1;
            return Math.max(1, cycleDay);
        } catch (Exception e) {
            return 1;
        }
    }

    public static String predictNextPeriod(String lastPeriodStr, int cycleLength, int delayDays) {
        try {
            LocalDate lastPeriod = LocalDate.parse(lastPeriodStr);
            LocalDate next = lastPeriod.plusDays(cycleLength + delayDays);
            return next.toString();
        } catch (Exception e) {
            return LocalDate.now().plusDays(cycleLength).toString();
        }
    }

    public static String predictOvulation(String lastPeriodStr, int cycleLength) {
        try {
            LocalDate lastPeriod = LocalDate.parse(lastPeriodStr);
            // Ovulation typically 14 days before next period
            LocalDate ovulation = lastPeriod.plusDays(cycleLength - 14);
            return ovulation.toString();
        } catch (Exception e) {
            return LocalDate.now().plusDays(14).toString();
        }
    }

    public static int getEventCycleDay(String lastPeriodStr, String eventDateStr, int cycleLength) {
        try {
            LocalDate lastPeriod = LocalDate.parse(lastPeriodStr);
            LocalDate eventDate = LocalDate.parse(eventDateStr);
            long daysDiff = ChronoUnit.DAYS.between(lastPeriod, eventDate);
            return (int)(daysDiff % cycleLength) + 1;
        } catch (Exception e) {
            return 1;
        }
    }

    public static int calculateDelay(
            double avgStress,
            double avgSleep,
            boolean hasEnvFactors,
            boolean highTrainingLoad) {

        int delay = 0;
        // High stress: cortisol suppresses reproductive hormones
        if (avgStress >= 7.0) delay += 2;
        else if (avgStress >= 5.0) delay += 1;

        // Poor sleep: affects hormonal regulation
        if (avgSleep < 4.0) delay += 2;
        else if (avgSleep < 6.0) delay += 1;

        // Environmental disruption
        if (hasEnvFactors) delay += 1;

        // Very high training load
        if (highTrainingLoad) delay += 1;

        return delay;
    }

    public static String getEventRecommendation(String phase) {
        switch (phase) {
            case "menstrual":
                return "Plan for lower energy and higher perceived effort. Prioritise iron intake and rest in the days before.";
            case "follicular":
                return "Rising energy phase - good performance expected. Train hard in the week before to arrive sharp.";
            case "ovulatory":
                return "Peak performance window - excellent timing! Always warm up thoroughly due to elevated ACL injury risk.";
            case "luteal":
                return "Manageable with preparation. Extra carbohydrates, longer warm-up, and prioritise sleep the week before.";
            default:
                return "Log more cycle data for personalised event recommendations.";
        }
    }

    public static String buildJson(
            String nextPeriod,
            String confidence,
            String ovulation,
            String currentPhase,
            int currentDay,
            String eventPhase,
            int eventDay,
            String eventRec,
            List<String> shiftFactors,
            List<String> alerts,
            List<String> injuryFlags,
            String summary) {

        StringBuilder sb = new StringBuilder();
        sb.append("{\n");
        sb.append("  \"next_period_predicted\": \"").append(escapeJson(nextPeriod)).append("\",\n");
        sb.append("  \"next_period_confidence\": \"").append(escapeJson(confidence)).append("\",\n");
        sb.append("  \"ovulation_estimated\": \"").append(escapeJson(ovulation)).append("\",\n");
        sb.append("  \"current_phase\": \"").append(escapeJson(currentPhase)).append("\",\n");
        sb.append("  \"current_phase_day\": ").append(currentDay).append(",\n");

        if (eventPhase != null && !eventPhase.isEmpty()) {
            sb.append("  \"event_phase_prediction\": \"").append(escapeJson(eventPhase)).append("\",\n");
            sb.append("  \"event_cycle_day_prediction\": ").append(eventDay).append(",\n");
            sb.append("  \"event_recommendations\": \"").append(escapeJson(eventRec)).append("\",\n");
        } else {
            sb.append("  \"event_phase_prediction\": null,\n");
            sb.append("  \"event_cycle_day_prediction\": null,\n");
            sb.append("  \"event_recommendations\": null,\n");
        }

        sb.append("  \"period_shift_factors\": ").append(listToJson(shiftFactors)).append(",\n");
        sb.append("  \"pattern_alerts\": ").append(listToJson(alerts)).append(",\n");
        sb.append("  \"injury_flags\": ").append(listToJson(injuryFlags)).append(",\n");
        sb.append("  \"summary\": \"").append(escapeJson(summary)).append("\"\n");
        sb.append("}");
        return sb.toString();
    }

    static String listToJson(List<String> items) {
        if (items == null || items.isEmpty()) return "[]";
        StringBuilder sb = new StringBuilder("[");
        for (int i = 0; i < items.size(); i++) {
            if (i > 0) sb.append(", ");
            sb.append("\"").append(escapeJson(items.get(i))).append("\"");
        }
        sb.append("]");
        return sb.toString();
    }

    static String escapeJson(String s) {
        if (s == null) return "";
        return s.replace("\\", "\\\\")
                .replace("\"", "\\\"")
                .replace("\n", "\\n")
                .replace("\r", "\\r")
                .replace("\t", "\\t");
    }

    /**
     * Main entry point — called by Python via:
     *   java CycleEngine <lastPeriod> <cycleLen> <avgStress> <avgSleep>
     *                    <hasEnv> <highLoad> [eventDate]
     * Prints JSON to stdout.
     */
    public static void main(String[] args) {
        if (args.length < 6) {
            System.out.println("{\"error\": \"Insufficient arguments\"}");
            System.exit(1);
        }

        String lastPeriod   = args[0];
        int    cycleLen     = Integer.parseInt(args[1]);
        double avgStress    = Double.parseDouble(args[2]);
        double avgSleep     = Double.parseDouble(args[3]);
        boolean hasEnv      = Boolean.parseBoolean(args[4]);
        boolean highLoad    = Boolean.parseBoolean(args[5]);
        String eventDate    = args.length > 6 ? args[6] : "";

        // Calculate delay from environmental and lifestyle factors
        int delay = calculateDelay(avgStress, avgSleep, hasEnv, highLoad);

        String nextPeriod  = predictNextPeriod(lastPeriod, cycleLen, delay);
        String ovulation   = predictOvulation(lastPeriod, cycleLen);
        int    currentDay  = getCycleDay(lastPeriod, cycleLen);
        String currentPhase = getPhase(currentDay);
        String confidence  = delay == 0 ? "high" : (delay <= 2 ? "medium" : "low");

        // Shift factors
        List<String> shiftFactors = new ArrayList<>();
        if (avgStress >= 7.0)  shiftFactors.add("High stress levels - possible 1 to 3 day delay");
        if (avgSleep < 5.0)    shiftFactors.add("Poor sleep quality - possible minor delay");
        if (hasEnv)            shiftFactors.add("Environmental factors noted - possible 1 to 2 day shift");
        if (highLoad)          shiftFactors.add("Heavy training load - possible minor delay");

        // Pattern alerts
        List<String> alerts = new ArrayList<>();
        if (avgStress >= 8.0)  alerts.add("Very high stress - monitor cycle timing closely");
        if (avgSleep < 4.0)    alerts.add("Critically low sleep - recovery and cycle regulation at risk");

        // Injury flags
        List<String> injuryFlags = new ArrayList<>();
        if (currentPhase.equals("ovulatory")) {
            injuryFlags.add("ACL and ligament injury risk elevated during ovulatory phase - warm up thoroughly");
        }

        // Event prediction
        String eventPhase = "";
        int    eventDay   = 0;
        String eventRec   = "";
        if (eventDate != null && !eventDate.isEmpty() && !eventDate.equals("null")) {
            try {
                eventDay  = getEventCycleDay(lastPeriod, eventDate, cycleLen);
                eventPhase = getPhase(eventDay);
                eventRec   = getEventRecommendation(eventPhase);
            } catch (Exception e) {
                eventPhase = "";
            }
        }

        String summary = "Predicted next period: " + nextPeriod + ". "
                + "Currently in " + currentPhase + " phase, day " + currentDay + ". "
                + (shiftFactors.isEmpty() ? "No adjustment factors." : shiftFactors.size() + " adjustment factor(s) applied.");

        System.out.println(buildJson(
                nextPeriod, confidence, ovulation,
                currentPhase, currentDay,
                eventPhase, eventDay, eventRec,
                shiftFactors, alerts, injuryFlags, summary
        ));
    }
}
