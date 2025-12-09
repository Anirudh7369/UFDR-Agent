"""
Case Analysis Tool - Comprehensive forensic case study and analytics
Generates detailed reports, heatmaps, and behavioral analysis across all data sources
"""

from __future__ import annotations

import logging
import pandas as pd
import numpy as np
import seaborn as sns
import matplotlib.pyplot as plt
from typing import Optional, Dict, List, Any
from pydantic import BaseModel, Field
from enum import Enum
from datetime import datetime
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box
from agents import function_tool
from pathlib import Path
from utils.db.connection import get_db_connection

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('forensic_case_tool.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

console = Console()

# Set matplotlib backend to Agg for non-GUI environments
plt.switch_backend('Agg')

# Set seaborn style
sns.set_style("whitegrid")
sns.set_palette("husl")


class AnalysisType(str, Enum):
    """Types of case analysis available"""
    COMPREHENSIVE = "comprehensive"
    COMMUNICATION = "communication"
    LOCATION = "location"
    BEHAVIOR = "behavior"
    TIMELINE = "timeline"
    HEATMAP = "heatmap"


class PersonProfile(BaseModel):
    """Profile of a person identified in the investigation"""
    identifier: str = Field(..., description="Phone number, username, or contact ID")
    name: Optional[str] = Field(None, description="Contact name if available")
    call_count: int = Field(0, description="Total number of calls")
    message_count: int = Field(0, description="Total number of messages")
    is_saved_contact: bool = Field(False, description="Whether contact is saved")
    most_active_hours: List[int] = Field(default_factory=list, description="Hours of peak activity")
    apps_used: List[str] = Field(default_factory=list, description="Apps used for communication")


class LocationHotspot(BaseModel):
    """Represents a location hotspot with activity metrics"""
    latitude: Optional[float] = Field(None, description="Latitude")
    longitude: Optional[float] = Field(None, description="Longitude")
    address: Optional[str] = Field(None, description="Address or location name")
    visit_count: int = Field(0, description="Number of visits")
    total_duration_minutes: Optional[float] = Field(None, description="Total time spent")
    apps_used: List[str] = Field(default_factory=list, description="Apps used at location")
    activities: List[str] = Field(default_factory=list, description="Activities at location")


class TimelineEvent(BaseModel):
    """Represents a significant event in the timeline"""
    timestamp: str = Field(..., description="Event timestamp")
    event_type: str = Field(..., description="Type of event (call, message, location, etc.)")
    description: str = Field(..., description="Event description")
    source_app: Optional[str] = Field(None, description="Source application")
    related_parties: List[str] = Field(default_factory=list, description="Related contacts")


class HeatmapData(BaseModel):
    """Heatmap data for activity visualization"""
    hourly_activity: Dict[int, int] = Field(default_factory=dict, description="Activity by hour (0-23)")
    daily_activity: Dict[str, int] = Field(default_factory=dict, description="Activity by day of week")
    app_usage: Dict[str, int] = Field(default_factory=dict, description="Activity by app")
    communication_patterns: Dict[str, int] = Field(default_factory=dict, description="Communication patterns")


class CaseAnalysisResult(BaseModel):
    """Comprehensive case analysis result"""
    analysis_type: str = Field(..., description="Type of analysis performed")
    summary: str = Field(..., description="Executive summary")
    top_contacts: List[PersonProfile] = Field(default_factory=list, description="Most contacted people")
    unknown_contacts: List[PersonProfile] = Field(default_factory=list, description="Unsaved contacts")
    location_hotspots: List[LocationHotspot] = Field(default_factory=list, description="Frequent locations")
    timeline: List[TimelineEvent] = Field(default_factory=list, description="Key timeline events")
    heatmap: HeatmapData = Field(default_factory=HeatmapData, description="Activity heatmap data")
    insights: List[str] = Field(default_factory=list, description="Key insights and patterns")
    recommendations: List[str] = Field(default_factory=list, description="Investigation recommendations")


async def analyze_communication_patterns(conn) -> Dict[str, Any]:
    """Analyze communication patterns across calls and messages"""
    logger.info("Analyzing communication patterns...")

    # Top contacts by call frequency
    call_query = """
        SELECT
            COALESCE(from_party_identifier, to_party_identifier) as identifier,
            COUNT(*) as call_count,
            source_app,
            ARRAY_AGG(DISTINCT EXTRACT(HOUR FROM to_timestamp(call_timestamp/1000))) as active_hours
        FROM call_logs
        WHERE from_party_identifier IS NOT NULL OR to_party_identifier IS NOT NULL
        GROUP BY identifier, source_app
        ORDER BY call_count DESC
        LIMIT 20
    """

    # Top contacts by message frequency
    message_query = """
        SELECT
            COALESCE(from_party_identifier, to_party_identifier) as identifier,
            COUNT(*) as message_count,
            source_app,
            ARRAY_AGG(DISTINCT EXTRACT(HOUR FROM to_timestamp(message_timestamp/1000))) as active_hours
        FROM messages
        WHERE from_party_identifier IS NOT NULL OR to_party_identifier IS NOT NULL
        GROUP BY identifier, source_app
        ORDER BY message_count DESC
        LIMIT 20
    """

    # Unknown contacts (not in contacts table)
    unknown_query = """
        WITH all_communications AS (
            SELECT DISTINCT from_party_identifier as identifier FROM call_logs
            UNION
            SELECT DISTINCT to_party_identifier FROM call_logs
            UNION
            SELECT DISTINCT from_party_identifier FROM messages
            UNION
            SELECT DISTINCT to_party_identifier FROM messages
        )
        SELECT ac.identifier
        FROM all_communications ac
        LEFT JOIN contact_entries ce ON ac.identifier = ce.value
        WHERE ce.value IS NULL AND ac.identifier IS NOT NULL
        LIMIT 50
    """

    call_results = await conn.fetch(call_query)
    message_results = await conn.fetch(message_query)
    unknown_results = await conn.fetch(unknown_query)

    return {
        "top_callers": call_results,
        "top_messagers": message_results,
        "unknown_contacts": unknown_results
    }


async def analyze_location_hotspots(conn) -> List[Dict[str, Any]]:
    """Analyze location hotspots and activity patterns"""
    logger.info("Analyzing location hotspots...")

    query = """
        SELECT
            latitude,
            longitude,
            address,
            source_app,
            COUNT(*) as visit_count,
            ARRAY_AGG(DISTINCT location_type) as activity_types
        FROM locations
        WHERE latitude IS NOT NULL AND longitude IS NOT NULL
        GROUP BY latitude, longitude, address, source_app
        HAVING COUNT(*) > 1
        ORDER BY visit_count DESC
        LIMIT 20
    """

    results = await conn.fetch(query)
    return [dict(row) for row in results]


async def generate_timeline(conn, limit: int = 100) -> List[Dict[str, Any]]:
    """Generate chronological timeline of all events"""
    logger.info("Generating timeline...")

    query = """
        WITH all_events AS (
            SELECT
                to_timestamp(call_timestamp/1000) as timestamp,
                'call' as event_type,
                source_app,
                CONCAT(call_type, ' call - ', status) as description,
                ARRAY[from_party_identifier, to_party_identifier] as parties
            FROM call_logs
            WHERE call_timestamp IS NOT NULL

            UNION ALL

            SELECT
                to_timestamp(message_timestamp/1000),
                'message' as event_type,
                source_app,
                CONCAT('Message',
                    CASE WHEN has_attachments THEN ' with attachment' ELSE '' END) as description,
                ARRAY[from_party_identifier, to_party_identifier] as parties
            FROM messages
            WHERE message_timestamp IS NOT NULL

            UNION ALL

            SELECT
                location_timestamp_dt,
                'location' as event_type,
                source_app,
                CONCAT('Location: ', COALESCE(address, 'Unknown')) as description,
                ARRAY[]::text[] as parties
            FROM locations
            WHERE location_timestamp_dt IS NOT NULL
        )
        SELECT *
        FROM all_events
        ORDER BY timestamp DESC
        LIMIT $1
    """

    results = await conn.fetch(query, limit)
    return [dict(row) for row in results]


async def generate_heatmap_data(conn) -> Dict[str, Any]:
    """Generate heatmap data for activity visualization"""
    logger.info("Generating heatmap data...")

    # Hourly activity
    hourly_query = """
        WITH all_activity AS (
            SELECT EXTRACT(HOUR FROM to_timestamp(call_timestamp/1000)) as hour FROM call_logs WHERE call_timestamp IS NOT NULL
            UNION ALL
            SELECT EXTRACT(HOUR FROM to_timestamp(message_timestamp/1000)) FROM messages WHERE message_timestamp IS NOT NULL
        )
        SELECT hour::int, COUNT(*)::int as count
        FROM all_activity
        GROUP BY hour
        ORDER BY hour
    """

    # Daily activity
    daily_query = """
        WITH all_activity AS (
            SELECT TO_CHAR(to_timestamp(call_timestamp/1000), 'Day') as day FROM call_logs WHERE call_timestamp IS NOT NULL
            UNION ALL
            SELECT TO_CHAR(to_timestamp(message_timestamp/1000), 'Day') FROM messages WHERE message_timestamp IS NOT NULL
        )
        SELECT TRIM(day) as day, COUNT(*)::int as count
        FROM all_activity
        GROUP BY day
        ORDER BY count DESC
    """

    # App usage
    app_query = """
        WITH all_activity AS (
            SELECT source_app FROM call_logs WHERE source_app IS NOT NULL
            UNION ALL
            SELECT source_app FROM messages WHERE source_app IS NOT NULL
        )
        SELECT source_app, COUNT(*)::int as count
        FROM all_activity
        GROUP BY source_app
        ORDER BY count DESC
    """

    hourly_results = await conn.fetch(hourly_query)
    daily_results = await conn.fetch(daily_query)
    app_results = await conn.fetch(app_query)

    return {
        "hourly": {row["hour"]: row["count"] for row in hourly_results},
        "daily": {row["day"]: row["count"] for row in daily_results},
        "apps": {row["source_app"]: row["count"] for row in app_results}
    }


async def generate_insights(data: Dict[str, Any]) -> List[str]:
    """Generate insights from analyzed data"""
    insights = []

    # Communication insights
    if data.get("top_callers"):
        top_caller = data["top_callers"][0]
        insights.append(
            f"Most frequent caller: {top_caller['identifier']} with {top_caller['call_count']} calls via {top_caller['source_app']}"
        )

    if data.get("top_messagers"):
        top_messager = data["top_messagers"][0]
        insights.append(
            f"Most frequent messager: {top_messager['identifier']} with {top_messager['message_count']} messages via {top_messager['source_app']}"
        )

    # Unknown contacts
    if data.get("unknown_contacts"):
        unknown_count = len(data["unknown_contacts"])
        insights.append(
            f"Found {unknown_count} unsaved contacts - potential persons of interest"
        )

    # Location insights
    if data.get("hotspots"):
        top_location = data["hotspots"][0]
        insights.append(
            f"Most visited location: {top_location.get('address', 'Unknown')} with {top_location['visit_count']} visits"
        )

    # Activity patterns
    if data.get("heatmap", {}).get("hourly"):
        hourly = data["heatmap"]["hourly"]
        peak_hour = max(hourly.items(), key=lambda x: x[1])[0]
        insights.append(
            f"Peak activity hour: {peak_hour}:00 - {peak_hour}:59"
        )

    return insights


def create_visualization_directory() -> Path:
    """Create directory for storing visualizations"""
    viz_dir = Path("forensic_visualizations")
    viz_dir.mkdir(exist_ok=True)
    return viz_dir


def generate_hourly_heatmap(hourly_data: Dict[int, int], output_path: Path) -> str:
    """Generate hourly activity heatmap visualization"""
    try:
        # Create DataFrame for hourly activity
        hours = list(range(24))
        activity = [hourly_data.get(h, 0) for h in hours]

        # Reshape data into a 2D grid (4 rows x 6 columns for 24 hours)
        activity_matrix = np.array(activity).reshape(4, 6)
        hour_labels = [[f"{h:02d}:00" for h in hours[i*6:(i+1)*6]] for i in range(4)]

        # Create heatmap
        fig, ax = plt.subplots(figsize=(14, 6))
        sns.heatmap(
            activity_matrix,
            annot=True,
            fmt='g',
            cmap='YlOrRd',
            xticklabels=[f"{h:02d}" for h in range(6)],
            yticklabels=[f"Row {i+1}" for i in range(4)],
            cbar_kws={'label': 'Activity Count'},
            linewidths=0.5,
            ax=ax
        )

        ax.set_title('24-Hour Activity Heatmap', fontsize=16, fontweight='bold', pad=20)
        ax.set_xlabel('Hour Block', fontsize=12)
        ax.set_ylabel('Time Period', fontsize=12)

        # Add custom hour labels
        for i in range(4):
            for j in range(6):
                hour = i * 6 + j
                ax.text(j + 0.5, i + 0.8, f"{hour:02d}:00",
                       ha='center', va='top', fontsize=8, color='black', alpha=0.6)

        plt.tight_layout()
        filepath = output_path / "hourly_activity_heatmap.png"
        plt.savefig(filepath, dpi=300, bbox_inches='tight')
        plt.close()

        logger.info(f"Hourly heatmap saved to {filepath}")
        return str(filepath)
    except Exception as e:
        logger.error(f"Error generating hourly heatmap: {e}")
        return ""


def generate_daily_activity_chart(daily_data: Dict[str, int], output_path: Path) -> str:
    """Generate daily activity bar chart"""
    try:
        # Order days correctly
        day_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        days = []
        counts = []

        for day in day_order:
            if day in daily_data:
                days.append(day[:3])  # Use abbreviated names
                counts.append(daily_data[day])

        if not days:
            return ""

        # Create bar chart
        fig, ax = plt.subplots(figsize=(12, 6))
        bars = ax.bar(days, counts, color=sns.color_palette('husl', len(days)))

        ax.set_title('Activity by Day of Week', fontsize=16, fontweight='bold', pad=20)
        ax.set_xlabel('Day of Week', fontsize=12)
        ax.set_ylabel('Activity Count', fontsize=12)
        ax.grid(axis='y', alpha=0.3)

        # Add value labels on bars
        for bar in bars:
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height,
                   f'{int(height)}',
                   ha='center', va='bottom', fontsize=10, fontweight='bold')

        plt.tight_layout()
        filepath = output_path / "daily_activity_chart.png"
        plt.savefig(filepath, dpi=300, bbox_inches='tight')
        plt.close()

        logger.info(f"Daily activity chart saved to {filepath}")
        return str(filepath)
    except Exception as e:
        logger.error(f"Error generating daily chart: {e}")
        return ""


def generate_app_usage_heatmap(app_data: Dict[str, int], output_path: Path) -> str:
    """Generate app usage distribution heatmap"""
    try:
        if not app_data:
            return ""

        # Sort by usage and take top 15
        sorted_apps = sorted(app_data.items(), key=lambda x: x[1], reverse=True)[:15]
        apps = [app for app, _ in sorted_apps]
        counts = [count for _, count in sorted_apps]

        # Create DataFrame for heatmap
        df = pd.DataFrame({
            'App': apps,
            'Usage': counts
        })

        # Create horizontal bar chart with heatmap coloring
        fig, ax = plt.subplots(figsize=(12, 8))

        # Normalize counts for color mapping
        norm_counts = np.array(counts) / max(counts) if counts else []
        colors = plt.cm.RdYlGn_r(norm_counts)

        bars = ax.barh(apps, counts, color=colors)

        ax.set_title('Top 15 Apps by Activity', fontsize=16, fontweight='bold', pad=20)
        ax.set_xlabel('Activity Count', fontsize=12)
        ax.set_ylabel('Application', fontsize=12)
        ax.grid(axis='x', alpha=0.3)

        # Add value labels
        for i, (bar, count) in enumerate(zip(bars, counts)):
            width = bar.get_width()
            ax.text(width, bar.get_y() + bar.get_height()/2.,
                   f' {int(count)}',
                   ha='left', va='center', fontsize=10, fontweight='bold')

        plt.tight_layout()
        filepath = output_path / "app_usage_heatmap.png"
        plt.savefig(filepath, dpi=300, bbox_inches='tight')
        plt.close()

        logger.info(f"App usage heatmap saved to {filepath}")
        return str(filepath)
    except Exception as e:
        logger.error(f"Error generating app usage heatmap: {e}")
        return ""


def generate_contact_communication_matrix(top_contacts: List[PersonProfile], output_path: Path) -> str:
    """Generate contact communication correlation matrix"""
    try:
        if len(top_contacts) < 2:
            return ""

        # Take top 10 contacts
        top_10 = top_contacts[:10]

        # Create data for heatmap
        data = []
        labels = []

        for contact in top_10:
            name = contact.name or contact.identifier[:15]
            labels.append(name)
            data.append([contact.call_count, contact.message_count])

        df = pd.DataFrame(data, columns=['Calls', 'Messages'], index=labels)

        # Create heatmap
        fig, ax = plt.subplots(figsize=(10, 8))
        sns.heatmap(
            df,
            annot=True,
            fmt='g',
            cmap='YlGnBu',
            cbar_kws={'label': 'Count'},
            linewidths=0.5,
            ax=ax
        )

        ax.set_title('Top 10 Contacts - Communication Heatmap', fontsize=16, fontweight='bold', pad=20)
        ax.set_xlabel('Communication Type', fontsize=12)
        ax.set_ylabel('Contact', fontsize=12)

        plt.tight_layout()
        filepath = output_path / "contact_communication_matrix.png"
        plt.savefig(filepath, dpi=300, bbox_inches='tight')
        plt.close()

        logger.info(f"Contact communication matrix saved to {filepath}")
        return str(filepath)
    except Exception as e:
        logger.error(f"Error generating contact matrix: {e}")
        return ""


def generate_location_heatmap(location_hotspots: List[LocationHotspot], output_path: Path) -> str:
    """Generate location hotspot visualization"""
    try:
        if len(location_hotspots) < 2:
            return ""

        # Take top 10 locations
        top_10 = location_hotspots[:10]

        labels = []
        visits = []

        for i, loc in enumerate(top_10, 1):
            label = loc.address[:30] if loc.address else f"Loc {i}"
            labels.append(label)
            visits.append(loc.visit_count)

        # Create bar chart
        fig, ax = plt.subplots(figsize=(12, 8))

        # Normalize for color mapping
        norm_visits = np.array(visits) / max(visits) if visits else []
        colors = plt.cm.OrRd(norm_visits)

        bars = ax.barh(labels, visits, color=colors)

        ax.set_title('Top 10 Location Hotspots', fontsize=16, fontweight='bold', pad=20)
        ax.set_xlabel('Visit Count', fontsize=12)
        ax.set_ylabel('Location', fontsize=12)
        ax.grid(axis='x', alpha=0.3)

        # Add value labels
        for bar, visit in zip(bars, visits):
            width = bar.get_width()
            ax.text(width, bar.get_y() + bar.get_height()/2.,
                   f' {int(visit)}',
                   ha='left', va='center', fontsize=10, fontweight='bold')

        plt.tight_layout()
        filepath = output_path / "location_hotspots.png"
        plt.savefig(filepath, dpi=300, bbox_inches='tight')
        plt.close()

        logger.info(f"Location hotspots saved to {filepath}")
        return str(filepath)
    except Exception as e:
        logger.error(f"Error generating location heatmap: {e}")
        return ""


def format_case_analysis_output(result: CaseAnalysisResult) -> str:
    """Format case analysis result as rich text output"""
    output = []

    # Header
    output.append("=" * 80)
    output.append("📊 FORENSIC CASE ANALYSIS REPORT")
    output.append("=" * 80)
    output.append(f"\nAnalysis Type: {result.analysis_type.upper()}\n")

    # Summary
    output.append("📋 EXECUTIVE SUMMARY")
    output.append("-" * 80)
    output.append(result.summary)
    output.append("")

    # Top Contacts
    if result.top_contacts:
        output.append("\n👥 TOP CONTACTS BY ACTIVITY")
        output.append("-" * 80)
        for i, contact in enumerate(result.top_contacts[:10], 1):
            name = contact.name or "Unknown"
            apps_display = ', '.join([app for app in contact.apps_used if app]) or "N/A"
            hours_display = ', '.join(map(str, contact.most_active_hours[:5])) or "N/A"
            output.append(
                f"{i}. {contact.identifier} ({name})\n"
                f"   📞 Calls: {contact.call_count} | 💬 Messages: {contact.message_count}\n"
                f"   📱 Apps: {apps_display}\n"
                f"   ⏰ Active Hours: {hours_display}"
            )
        output.append("")

    # Unknown Contacts
    if result.unknown_contacts:
        output.append("\n⚠️  UNSAVED CONTACTS (PERSONS OF INTEREST)")
        output.append("-" * 80)
        for i, contact in enumerate(result.unknown_contacts[:10], 1):
            apps_display = ', '.join([app for app in contact.apps_used if app]) or "N/A"
            output.append(
                f"{i}. {contact.identifier}\n"
                f"   📞 Calls: {contact.call_count} | 💬 Messages: {contact.message_count}\n"
                f"   📱 Apps: {apps_display}"
            )
        output.append("")

    # Location Hotspots
    if result.location_hotspots:
        output.append("\n📍 LOCATION HOTSPOTS")
        output.append("-" * 80)
        for i, location in enumerate(result.location_hotspots[:10], 1):
            addr = location.address or f"({location.latitude}, {location.longitude})"
            apps_display = ', '.join([app for app in location.apps_used if app]) or "N/A"
            activities_display = ', '.join([act for act in location.activities if act]) or "N/A"
            output.append(
                f"{i}. {addr}\n"
                f"   🔄 Visits: {location.visit_count}\n"
                f"   📱 Apps: {apps_display}\n"
                f"   🎯 Activities: {activities_display}"
            )
        output.append("")

    # Heatmap Data
    if result.heatmap:
        output.append("\n🔥 ACTIVITY HEATMAP")
        output.append("-" * 80)

        if result.heatmap.hourly_activity:
            output.append("⏰ Hourly Activity Pattern:")
            sorted_hours = sorted(result.heatmap.hourly_activity.items())
            for hour, count in sorted_hours[:10]:
                bar = "█" * min(50, count // 10)
                output.append(f"  {hour:02d}:00 | {bar} {count}")

        if result.heatmap.app_usage:
            output.append("\n📱 App Usage Distribution:")
            sorted_apps = sorted(result.heatmap.app_usage.items(), key=lambda x: x[1], reverse=True)
            for app, count in sorted_apps[:10]:
                bar = "█" * min(50, count // 10)
                output.append(f"  {app:20s} | {bar} {count}")

        output.append("")

    # Timeline
    if result.timeline:
        output.append("\n📅 RECENT TIMELINE (Last 20 Events)")
        output.append("-" * 80)
        for event in result.timeline[:20]:
            parties = ", ".join([p for p in event.related_parties if p]) or "N/A"
            output.append(
                f"⏱️  {event.timestamp}\n"
                f"   Type: {event.event_type} | App: {event.source_app or 'N/A'}\n"
                f"   {event.description}\n"
                f"   Parties: {parties}\n"
            )

    # Insights
    if result.insights:
        output.append("\n💡 KEY INSIGHTS")
        output.append("-" * 80)
        for i, insight in enumerate(result.insights, 1):
            output.append(f"{i}. {insight}")
        output.append("")

    # Recommendations
    if result.recommendations:
        output.append("\n🎯 INVESTIGATION RECOMMENDATIONS")
        output.append("-" * 80)
        for i, rec in enumerate(result.recommendations, 1):
            output.append(f"{i}. {rec}")
        output.append("")

    output.append("=" * 80)
    output.append("📊 END OF REPORT")
    output.append("=" * 80)

    return "\n".join(output)


@function_tool
async def generate_case_analysis(
    analysis_type: str = "comprehensive",
    include_timeline: bool = True,
    include_heatmap: bool = True,
    generate_visualizations: bool = True,
    max_contacts: int = 20
) -> str:
    """
    Generate comprehensive case analysis by analyzing data across all forensic sources.

    Args:
        analysis_type: Type of analysis - "comprehensive", "communication", "location", "behavior", "timeline", or "heatmap"
        include_timeline: Whether to include chronological timeline
        include_heatmap: Whether to include activity heatmap
        generate_visualizations: Whether to generate Seaborn heatmap visualizations (default: True)
        max_contacts: Maximum number of contacts to analyze (default: 20, max: 100)

    Returns:
        Formatted case analysis report with insights, patterns, recommendations, and visual heatmap files
    """
    try:
        logger.info(f"Starting case analysis: {analysis_type}")

        # Validate analysis type
        if analysis_type not in [t.value for t in AnalysisType]:
            return f"❌ Invalid analysis type. Must be one of: {', '.join([t.value for t in AnalysisType])}"

        # Limit max_contacts
        max_contacts = min(max_contacts, 100)

        async with get_db_connection() as conn:
            # Gather data based on analysis type
            data = {}

            if analysis_type in ["comprehensive", "communication", "behavior"]:
                comm_data = await analyze_communication_patterns(conn)
                data.update(comm_data)

            if analysis_type in ["comprehensive", "location", "behavior"]:
                hotspots = await analyze_location_hotspots(conn)
                data["hotspots"] = hotspots

            if analysis_type in ["comprehensive", "timeline"] and include_timeline:
                timeline_data = await generate_timeline(conn, limit=100)
                data["timeline"] = timeline_data

            if analysis_type in ["comprehensive", "heatmap", "behavior"] and include_heatmap:
                heatmap_data = await generate_heatmap_data(conn)
                data["heatmap"] = heatmap_data

            # Build PersonProfile objects
            top_contacts = []
            unknown_contacts = []

            # Process top contacts
            contact_map = {}
            for caller in data.get("top_callers", [])[:max_contacts]:
                identifier = caller["identifier"]
                if identifier not in contact_map:
                    contact_map[identifier] = PersonProfile(
                        identifier=identifier,
                        call_count=0,
                        message_count=0,
                        apps_used=[],
                        most_active_hours=[]
                    )
                contact_map[identifier].call_count += caller["call_count"]
                if caller.get("source_app"):
                    contact_map[identifier].apps_used.append(caller["source_app"])
                contact_map[identifier].most_active_hours.extend(caller.get("active_hours", []))

            for messager in data.get("top_messagers", [])[:max_contacts]:
                identifier = messager["identifier"]
                if identifier not in contact_map:
                    contact_map[identifier] = PersonProfile(
                        identifier=identifier,
                        call_count=0,
                        message_count=0,
                        apps_used=[],
                        most_active_hours=[]
                    )
                contact_map[identifier].message_count += messager["message_count"]
                if messager.get("source_app"):
                    contact_map[identifier].apps_used.append(messager["source_app"])
                contact_map[identifier].most_active_hours.extend(messager.get("active_hours", []))

            # Sort by total activity
            top_contacts = sorted(
                contact_map.values(),
                key=lambda x: x.call_count + x.message_count,
                reverse=True
            )[:max_contacts]

            # Process unknown contacts
            for unknown in data.get("unknown_contacts", []):
                unknown_contacts.append(PersonProfile(
                    identifier=unknown["identifier"],
                    is_saved_contact=False
                ))

            # Build LocationHotspot objects
            location_hotspots = []
            for hotspot in data.get("hotspots", [])[:20]:
                # Filter out None values from activities
                activities = [a for a in hotspot.get("activity_types", []) if a is not None]
                # Filter out None values from apps_used
                apps = [hotspot["source_app"]] if hotspot.get("source_app") is not None else []
                location_hotspots.append(LocationHotspot(
                    latitude=hotspot.get("latitude"),
                    longitude=hotspot.get("longitude"),
                    address=hotspot.get("address"),
                    visit_count=hotspot["visit_count"],
                    apps_used=apps,
                    activities=activities
                ))

            # Build Timeline objects
            timeline = []
            for event in data.get("timeline", [])[:100]:
                timeline.append(TimelineEvent(
                    timestamp=str(event["timestamp"]),
                    event_type=event["event_type"],
                    description=event["description"],
                    source_app=event.get("source_app"),
                    related_parties=[p for p in event.get("parties", []) if p]
                ))

            # Build HeatmapData
            heatmap = HeatmapData(
                hourly_activity=data.get("heatmap", {}).get("hourly", {}),
                daily_activity=data.get("heatmap", {}).get("daily", {}),
                app_usage=data.get("heatmap", {}).get("apps", {})
            )

            # Generate insights
            insights = await generate_insights(data)

            # Generate recommendations
            recommendations = [
                "Investigate unsaved contacts for potential hidden relationships",
                "Cross-reference location hotspots with communication patterns",
                "Analyze peak activity hours for behavioral patterns",
                "Review timeline for suspicious activity clusters",
                "Examine deleted messages and calls for evidence tampering"
            ]

            # Build summary
            summary = f"""
This {analysis_type} analysis examined data across all forensic sources including:
- Call logs, messages, contacts, locations, browsing history, and installed apps
- Total unique contacts analyzed: {len(top_contacts)}
- Unsaved contacts identified: {len(unknown_contacts)}
- Location hotspots found: {len(location_hotspots)}
- Timeline events: {len(timeline)}

The analysis reveals communication patterns, location behavior, and activity trends
that provide critical insights for the investigation.
            """.strip()

            # Create result
            result = CaseAnalysisResult(
                analysis_type=analysis_type,
                summary=summary,
                top_contacts=top_contacts,
                unknown_contacts=unknown_contacts,
                location_hotspots=location_hotspots,
                timeline=timeline,
                heatmap=heatmap,
                insights=insights,
                recommendations=recommendations
            )

            # Generate visualizations if requested
            visualization_paths = []
            if generate_visualizations:
                try:
                    logger.info("Generating visual analytics...")
                    viz_dir = create_visualization_directory()

                    # Generate hourly activity heatmap
                    if result.heatmap.hourly_activity:
                        hourly_path = generate_hourly_heatmap(result.heatmap.hourly_activity, viz_dir)
                        if hourly_path:
                            visualization_paths.append(hourly_path)

                    # Generate daily activity chart
                    if result.heatmap.daily_activity:
                        daily_path = generate_daily_activity_chart(result.heatmap.daily_activity, viz_dir)
                        if daily_path:
                            visualization_paths.append(daily_path)

                    # Generate app usage heatmap
                    if result.heatmap.app_usage:
                        app_path = generate_app_usage_heatmap(result.heatmap.app_usage, viz_dir)
                        if app_path:
                            visualization_paths.append(app_path)

                    # Generate contact communication matrix
                    if len(result.top_contacts) >= 2:
                        contact_path = generate_contact_communication_matrix(result.top_contacts, viz_dir)
                        if contact_path:
                            visualization_paths.append(contact_path)

                    # Generate location hotspots
                    if len(result.location_hotspots) >= 2:
                        location_path = generate_location_heatmap(result.location_hotspots, viz_dir)
                        if location_path:
                            visualization_paths.append(location_path)

                    logger.info(f"Generated {len(visualization_paths)} visualizations")
                except Exception as viz_error:
                    logger.error(f"Error generating visualizations: {viz_error}")

            # Format and return
            output = format_case_analysis_output(result)

            # Add visualization info to output
            if visualization_paths:
                output += "\n\n" + "=" * 80 + "\n"
                output += "📈 VISUAL ANALYTICS GENERATED\n"
                output += "=" * 80 + "\n\n"
                output += "The following Seaborn heatmap visualizations have been generated:\n\n"
                for i, path in enumerate(visualization_paths, 1):
                    filename = Path(path).name
                    output += f"{i}. {filename}\n   📁 {path}\n\n"
                output += "These high-resolution PNG files provide visual insights into:\n"
                output += "- 24-hour activity patterns (heatmap)\n"
                output += "- Daily activity distribution (bar chart)\n"
                output += "- Top app usage patterns (color-coded bars)\n"
                output += "- Contact communication matrix (calls vs messages)\n"
                output += "- Location hotspots (visit frequency)\n\n"
                output += "Use these visualizations for presentations, reports, or detailed analysis.\n"
                output += "=" * 80 + "\n"

            logger.info("Case analysis completed successfully")

            return output

    except Exception as e:
        error_msg = f"❌ Error generating case analysis: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return error_msg


# Export the tool
case_tool = generate_case_analysis
