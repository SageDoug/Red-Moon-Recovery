/*
 * Red Moon Recovery - Pattern Analyzer (C++)
 * Analyzes journal entry data passed as JSON via stdin.
 * Outputs pattern analysis as JSON to stdout.
 * Called from Python via subprocess.
 *
 * Compile: g++ -o pattern_analyzer pattern_analyzer.cpp -std=c++17
 * Usage:   echo '<json>' | ./pattern_analyzer
 */

#include <iostream>
#include <string>
#include <vector>
#include <sstream>
#include <algorithm>
#include <numeric>
#include <cmath>
#include <regex>
#include <iomanip>

// ── Simple JSON value extractor ──
// Extracts a string or number value from a flat JSON string by key name.

std::string extractStr(const std::string& json, const std::string& key) {
    std::string pattern = "\"" + key + "\"\\s*:\\s*\"([^\"]*?)\"";
    std::regex re(pattern);
    std::smatch m;
    if (std::regex_search(json, m, re)) return m[1].str();
    return "";
}

double extractNum(const std::string& json, const std::string& key, double def = 0.0) {
    std::string pattern = "\"" + key + "\"\\s*:\\s*([0-9.\\-]+)";
    std::regex re(pattern);
    std::smatch m;
    if (std::regex_search(json, m, re)) {
        try { return std::stod(m[1].str()); }
        catch (...) { return def; }
    }
    return def;
}

// Extract all JSON objects from an array field
std::vector<std::string> extractArray(const std::string& json, const std::string& key) {
    std::vector<std::string> results;
    std::string search = "\"" + key + "\"\\s*:\\s*\\[";
    std::regex startRe(search);
    std::smatch startMatch;
    if (!std::regex_search(json, startMatch, startRe)) return results;

    size_t pos = startMatch.position() + startMatch.length();
    int depth = 1;
    size_t objStart = std::string::npos;
    bool inStr = false;
    char prev = 0;

    for (size_t i = pos; i < json.size() && depth > 0; i++) {
        char c = json[i];
        if (c == '"' && prev != '\\') inStr = !inStr;
        if (!inStr) {
            if (c == '{') {
                if (depth == 1) objStart = i;
                depth++;
            } else if (c == '}') {
                depth--;
                if (depth == 1 && objStart != std::string::npos) {
                    results.push_back(json.substr(objStart, i - objStart + 1));
                    objStart = std::string::npos;
                }
            } else if (c == ']' && depth == 1) {
                depth--;
            }
        }
        prev = c;
    }
    return results;
}

std::string escapeJson(const std::string& s) {
    std::string out;
    for (char c : s) {
        if (c == '"') out += "\\\"";
        else if (c == '\\') out += "\\\\";
        else if (c == '\n') out += "\\n";
        else out += c;
    }
    return out;
}

std::string vecToJson(const std::vector<std::string>& v) {
    std::string out = "[";
    for (size_t i = 0; i < v.size(); i++) {
        if (i > 0) out += ",";
        out += "\"" + escapeJson(v[i]) + "\"";
    }
    out += "]";
    return out;
}

// ── Analysis functions ──

struct PatternResult {
    std::vector<std::string> patterns;
    std::vector<std::string> warnings;
    std::vector<std::string> recommendations;
    double avgSleep     = 0.0;
    double avgRPE       = 0.0;
    double avgMotivation = 0.0;
    double avgStress    = 0.0;
    int    entryCount   = 0;
    bool   hasInjury    = false;
    bool   hasEnvFactors = false;
    bool   highLoad     = false;
};

PatternResult analyze(const std::vector<std::string>& entries) {
    PatternResult result;
    result.entryCount = static_cast<int>(entries.size());

    if (entries.empty()) {
        result.patterns.push_back("No journal entries found yet");
        result.recommendations.push_back("Start logging daily to unlock pattern analysis");
        return result;
    }

    // Collect numeric series
    std::vector<double> sleepVals, rpeVals, motVals, stressVals;
    int lowEnergyCount  = 0;
    int sharpPainCount  = 0;
    int highRPELowMotCount = 0;
    bool foundInjury = false;
    bool foundEnv    = false;

    for (const auto& entry : entries) {
        double sq = extractNum(entry, "sleep_quality", -1);
        double rpe = extractNum(entry, "rpe", -1);
        double mot = extractNum(entry, "motivation", -1);
        double stress = extractNum(entry, "stress_level", -1);

        if (sq > 0)  sleepVals.push_back(sq);
        if (rpe > 0) rpeVals.push_back(rpe);
        if (mot > 0) motVals.push_back(mot);
        if (stress > 0) stressVals.push_back(stress);

        std::string energy   = extractStr(entry, "energy");
        std::string soreness = extractStr(entry, "soreness");
        std::string injuries = extractStr(entry, "injuries");
        std::string envNotes = extractStr(entry, "environmental_notes");
        std::string load     = extractStr(entry, "training_load");

        // Lowercase for comparison
        std::transform(energy.begin(), energy.end(), energy.begin(), ::tolower);
        std::transform(soreness.begin(), soreness.end(), soreness.begin(), ::tolower);
        std::transform(injuries.begin(), injuries.end(), injuries.begin(), ::tolower);

        if (energy.find("low") != std::string::npos) lowEnergyCount++;
        if (soreness.find("sharp") != std::string::npos) sharpPainCount++;
        if (!injuries.empty() && injuries != "none" && injuries != "no") foundInjury = true;
        if (!envNotes.empty()) foundEnv = true;
        if (rpe > 0 && mot > 0 && rpe >= 8 && mot <= 4) highRPELowMotCount++;
    }

    // Calculate averages
    auto avg = [](const std::vector<double>& v) -> double {
        if (v.empty()) return 0.0;
        return std::accumulate(v.begin(), v.end(), 0.0) / v.size();
    };

    result.avgSleep      = avg(sleepVals);
    result.avgRPE        = avg(rpeVals);
    result.avgMotivation = avg(motVals);
    result.avgStress     = avg(stressVals);
    result.hasInjury     = foundInjury;
    result.hasEnvFactors = foundEnv;
    result.highLoad      = (result.avgRPE > 7.5);

    // Generate patterns
    char buf[256];

    if (!sleepVals.empty() && result.avgSleep < 5.5) {
        snprintf(buf, sizeof(buf), "Consistently low sleep quality (avg %.1f/10)", result.avgSleep);
        result.patterns.push_back(buf);
        result.warnings.push_back("Poor sleep is suppressing recovery and may delay your next period");
        result.recommendations.push_back("Prioritise sleep consistency. Keep room cool especially in luteal phase");
    }

    if (lowEnergyCount >= 3) {
        snprintf(buf, sizeof(buf), "Persistent low energy across %d recent days", lowEnergyCount);
        result.patterns.push_back(buf);
        result.recommendations.push_back("Check nutrition timing, iron levels, and training load for your current cycle phase");
    }

    if (sharpPainCount >= 2) {
        result.patterns.push_back("Recurring sharp or specific pain across multiple entries");
        result.warnings.push_back("Recurring sharp pain may indicate an injury that needs assessment");
        result.recommendations.push_back("Consider reducing training load and getting the area assessed by a physio");
    }

    if (highRPELowMotCount >= 2) {
        result.patterns.push_back("Training at high effort despite very low motivation - possible overreach");
        result.warnings.push_back("High RPE with low motivation is an early overtraining signal");
        result.recommendations.push_back("Insert a planned deload or active recovery day this week");
    }

    if (!stressVals.empty() && result.avgStress >= 7.0) {
        snprintf(buf, sizeof(buf), "High average stress (%.1f/10) which can disrupt cycle timing", result.avgStress);
        result.patterns.push_back(buf);
        result.warnings.push_back("High stress elevates cortisol which suppresses reproductive hormones and can delay ovulation");
    }

    if (foundInjury) {
        result.patterns.push_back("Active or recent injuries noted in journal entries");
        result.recommendations.push_back("Factor injury into training load and monitor for changes day to day");
    }

    if (foundEnv) {
        result.patterns.push_back("Environmental factors have been logged - factored into cycle predictions");
    }

    if (!rpeVals.empty() && result.avgRPE > 8.0) {
        result.patterns.push_back("Sustained very high training intensity - recovery may be insufficient");
        result.recommendations.push_back("A deload week every 4 to 6 weeks is recommended to prevent accumulated fatigue");
    }

    if (result.patterns.empty()) {
        result.patterns.push_back("No concerning patterns detected in recent entries");
        result.recommendations.push_back("Keep logging consistently to maintain accuracy");
    }

    return result;
}

int main() {
    // Read all of stdin
    std::string input;
    std::string line;
    while (std::getline(std::cin, line)) {
        input += line + "\n";
    }

    // Extract entries array
    std::vector<std::string> entries = extractArray(input, "entries");

    PatternResult result = analyze(entries);

    // Output JSON
    std::cout << "{\n";
    std::cout << "  \"entry_count\": " << result.entryCount << ",\n";
    std::cout << "  \"avg_sleep\": " << std::fixed << std::setprecision(1) << result.avgSleep << ",\n";
    std::cout << "  \"avg_rpe\": " << result.avgRPE << ",\n";
    std::cout << "  \"avg_motivation\": " << result.avgMotivation << ",\n";
    std::cout << "  \"avg_stress\": " << result.avgStress << ",\n";
    std::cout << "  \"has_injury\": " << (result.hasInjury ? "true" : "false") << ",\n";
    std::cout << "  \"has_env_factors\": " << (result.hasEnvFactors ? "true" : "false") << ",\n";
    std::cout << "  \"high_load\": " << (result.highLoad ? "true" : "false") << ",\n";
    std::cout << "  \"patterns\": " << vecToJson(result.patterns) << ",\n";
    std::cout << "  \"warnings\": " << vecToJson(result.warnings) << ",\n";
    std::cout << "  \"recommendations\": " << vecToJson(result.recommendations) << "\n";
    std::cout << "}\n";

    return 0;
}
