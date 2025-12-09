case_tool_prompt = """
# Case Analysis Tool - Usage Guide

## Tool Purpose

This tool generates **comprehensive forensic case studies** by analyzing data across ALL sources (calls, messages, contacts, locations, browsing, apps). Use it for:
- Complete case reports and summaries
- Behavioral analysis and patterns
- Activity heatmaps and visualizations
- Identifying key persons of interest
- Location-based behavioral studies
- Timeline reconstruction
- Communication network analysis

## Tool Parameters

The tool has 5 parameters:
- **analysis_type** (optional): Type of analysis to perform (default: "comprehensive")
- **include_timeline** (optional): Include chronological timeline (default: true)
- **include_heatmap** (optional): Include activity heatmap (default: true)
- **generate_visualizations** (optional): Generate Seaborn visual heatmaps as PNG files (default: true)
- **max_contacts** (optional): Maximum contacts to analyze (default: 20, max: 100)

## Analysis Types

1. **comprehensive** (default) - Full analysis across all data sources
   - Communication patterns (calls + messages)
   - Location hotspots
   - Timeline of events
   - Activity heatmaps
   - Top contacts and unknown contacts
   - Behavioral insights

2. **communication** - Focus on communication patterns
   - Most contacted people
   - Message and call frequency
   - Unsaved contacts
   - Communication apps used
   - Active hours analysis

3. **location** - Focus on location behavior
   - Most visited locations
   - Location hotspots
   - Apps used at each location
   - Visit frequency

4. **behavior** - Focus on behavioral patterns
   - Activity heatmaps
   - Peak activity hours
   - Daily patterns
   - App usage patterns
   - Communication + location correlation

5. **timeline** - Chronological reconstruction
   - All events in order
   - Calls, messages, locations combined
   - Event descriptions and parties

6. **heatmap** - Activity visualization data
   - Hourly activity distribution
   - Daily activity distribution
   - App usage distribution
   - Communication patterns

## What This Tool Provides

### 📊 Executive Summary
- Overview of data analyzed
- Total contacts, locations, events
- Key findings at a glance

### 👥 Top Contacts Analysis
- Most frequently contacted people
- Call and message counts
- Apps used for each contact
- Active hours for each contact
- Saved vs unsaved status

### ⚠️ Unknown Contacts (Persons of Interest)
- People who are NOT saved in contacts
- Communication frequency
- Potential hidden relationships
- Apps used

### 📍 Location Hotspots
- Most frequently visited locations
- Visit counts
- Apps used at each location
- Activities at each location

### 📅 Timeline
- Chronological list of all events
- Calls, messages, locations combined
- Timestamps and descriptions
- Related parties

### 🔥 Activity Heatmap
- Hour-by-hour activity patterns
- Day-by-day activity patterns
- App usage distribution
- Visual representation of behavior

### 📈 Visual Analytics (Seaborn Heatmaps)
When `generate_visualizations=True` (default), the tool creates high-resolution PNG visualizations:
- **24-Hour Activity Heatmap** - Color-coded grid showing activity by hour
- **Daily Activity Bar Chart** - Activity distribution across days of the week
- **App Usage Heatmap** - Top 15 apps with color-coded usage intensity
- **Contact Communication Matrix** - Calls vs messages for top 10 contacts
- **Location Hotspots Chart** - Visit frequency for top locations

All visualizations are saved in the `forensic_visualizations/` directory and use professional Seaborn styling with clear labels and color gradients for easy pattern recognition.

### 💡 Key Insights
- Automated pattern detection
- Behavioral observations
- Suspicious patterns
- Critical findings

### 🎯 Investigation Recommendations
- Suggested next steps
- Areas requiring deeper investigation
- Cross-reference opportunities

## When to Use This Tool

### ✅ USE when user asks for:
- "Generate a case report"
- "Give me a comprehensive analysis"
- "Show me the complete picture"
- "Who does this person communicate with most?"
- "What are the location patterns?"
- "Show me a heatmap of activity"
- "Who are the persons of interest?"
- "Unsaved contacts"
- "Behavioral study"
- "Communication patterns"
- "Timeline of events"
- "Complete summary"
- "Case study"

### ❌ DON'T USE when user asks for:
- Specific data queries (use individual tools instead)
- "Show WhatsApp messages" → use query_messages
- "Show call logs" → use query_call_logs
- "Show locations on date X" → use query_locations

## Query Examples

1. **"Generate a comprehensive case report"**
   → `generate_case_analysis(analysis_type="comprehensive")`

2. **"Show me communication patterns"**
   → `generate_case_analysis(analysis_type="communication")`

3. **"Who are the persons of interest?"**
   → `generate_case_analysis(analysis_type="communication", max_contacts=50)`

4. **"Give me a behavioral analysis"**
   → `generate_case_analysis(analysis_type="behavior")`

5. **"Show activity heatmap"**
   → `generate_case_analysis(analysis_type="heatmap")`

6. **"Generate timeline of events"**
   → `generate_case_analysis(analysis_type="timeline", include_heatmap=False)`

7. **"What are the location hotspots?"**
   → `generate_case_analysis(analysis_type="location")`

8. **"Complete case study with all details"**
   → `generate_case_analysis(analysis_type="comprehensive", max_contacts=100)`

9. **"Generate report without visualizations"**
   → `generate_case_analysis(analysis_type="comprehensive", generate_visualizations=False)`

## Important Notes

- This tool queries ALL data sources and can take longer to execute
- Results are comprehensive and may be lengthy
- Use specific analysis types to focus on particular aspects
- Default analysis_type="comprehensive" provides full picture
- Unsaved contacts are automatically identified as persons of interest
- Heatmap data helps identify behavioral patterns
- Timeline combines all event types chronologically
- **Visual Analytics**: By default, generates 5 high-resolution Seaborn heatmap PNG files saved to `forensic_visualizations/` directory
- Visualizations use professional styling with color gradients (YlOrRd, YlGnBu, OrRd, etc.) for pattern recognition
- All charts are 300 DPI for presentation quality
"""
