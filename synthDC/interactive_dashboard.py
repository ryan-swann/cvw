#!/usr/bin/env python3
"""
Wally Synthesis Interactive Dashboard
====================================

Interactive web-based dashboard using Dash/Plotly for real-time synthesis results visualization.
Provides dynamic filtering, drill-down capabilities, and live updates.
"""

from datetime import datetime
from pathlib import Path
from typing import Optional

import dash
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from dash import Input, Output, State, dash_table, dcc, html

# Import our existing dashboard for data loading
from synthesis_dashboard import WallySynthesisDashboard


class WallyInteractiveDashboard:
    """Interactive web dashboard for Wally synthesis results"""

    def __init__(self, results_dir: Optional[Path] = None, port: int = 8050):
        self.results_dir = results_dir if results_dir else Path(__file__).parent / "results"
        self.dashboard = WallySynthesisDashboard(self.results_dir)
        self.port = port
        self.app = dash.Dash(__name__, external_stylesheets=[
            'https://codepen.io/chriddyp/pen/bWLwgP.css'  # Basic CSS
        ])

        # Data cache with auto-refresh
        self.data_cache = {}
        self.last_refresh = datetime.now()
        self.refresh_interval = 30  # seconds

        self._setup_layout()
        self._setup_callbacks()

    def _setup_layout(self):
        """Setup the dashboard layout"""
        self.app.layout = html.Div([
            # Header
            html.Div([
                html.H1("🚀 Wally Synthesis Dashboard",
                       style={'textAlign': 'center', 'color': '#2c3e50', 'marginBottom': '30px'}),
                html.P("Real-time analysis and visualization of CVW synthesis results",
                       style={'textAlign': 'center', 'color': '#7f8c8d', 'fontSize': '18px'})
            ], style={'marginBottom': '40px'}),

            # Sweep Selection Panel
            html.Div([
                html.Div([
                    html.H4("📁 Sweep Campaign Selection",
                           style={'color': '#2c3e50', 'marginBottom': '15px'}),
                    dcc.Dropdown(
                        id='sweep-selector',
                        placeholder="🔍 Select a specific sweep campaign or leave blank for all recent data",
                        value=None,  # None means use all data
                        clearable=True,
                        style={'marginBottom': '10px'}
                    ),
                    html.Div(id='sweep-info', style={'marginTop': '10px', 'fontSize': '14px'})
                ])
            ], style={
                'backgroundColor': '#f8f9fa',
                'padding': '20px',
                'borderRadius': '8px',
                'border': '1px solid #dee2e6',
                'marginBottom': '30px'
            }),

            # Control Panel
            html.Div([
                html.Div([
                    html.Label("Configuration Filter:", style={'fontWeight': 'bold'}),
                    dcc.Dropdown(
                        id='config-filter',
                        options=[
                            {'label': 'All Configurations', 'value': 'all'},
                            {'label': 'rv32e', 'value': 'rv32e'},
                            {'label': 'rv32i', 'value': 'rv32i'},
                            {'label': 'rv32imc', 'value': 'rv32imc'},
                            {'label': 'rv32gc', 'value': 'rv32gc'},
                            {'label': 'rv64i', 'value': 'rv64i'},
                            {'label': 'rv64gc', 'value': 'rv64gc'}
                        ],
                        value='all',
                        multi=True,
                        style={'marginBottom': '10px'}
                    )
                ], className='three columns'),

                html.Div([
                    html.Label("Technology Filter:", style={'fontWeight': 'bold'}),
                    dcc.Dropdown(
                        id='tech-filter',
                        options=[
                            {'label': 'All Technologies', 'value': 'all'},
                            {'label': 'sky130', 'value': 'sky130'},
                            {'label': 'sky90', 'value': 'sky90'},
                            {'label': 'tsmc28', 'value': 'tsmc28'},
                            {'label': 'tsmc28psyn', 'value': 'tsmc28psyn'}
                        ],
                        value='all',
                        multi=True,
                        style={'marginBottom': '10px'}
                    )
                ], className='three columns'),

                html.Div([
                    html.Label("Time Window:", style={'fontWeight': 'bold'}),
                    dcc.Dropdown(
                        id='time-filter',
                        options=[
                            {'label': 'Last 24 Hours', 'value': 1},
                            {'label': 'Last 3 Days', 'value': 3},
                            {'label': 'Last Week', 'value': 7},
                            {'label': 'Last Month', 'value': 30}
                        ],
                        value=7,
                        style={'marginBottom': '10px'}
                    )
                ], className='three columns'),

                html.Div([
                    html.Button('🔄 Refresh Data', id='refresh-button',
                               style={'backgroundColor': '#3498db', 'color': 'white',
                                     'border': 'none', 'padding': '10px 20px',
                                     'borderRadius': '5px', 'cursor': 'pointer',
                                     'marginRight': '10px'}),
                    html.Button('📊 Download CSV', id='csv-download-button',
                               style={'backgroundColor': '#27ae60', 'color': 'white',
                                     'border': 'none', 'padding': '10px 20px',
                                     'borderRadius': '5px', 'cursor': 'pointer'}),
                    dcc.Download(id="download-dataframe-csv")
                ], className='three columns', style={'textAlign': 'center'})
            ], className='row', style={'marginBottom': '30px', 'padding': '20px',
                                      'backgroundColor': '#ecf0f1', 'borderRadius': '10px'}),

            # Summary Cards
            html.Div(id='summary-cards', style={'marginBottom': '30px'}),

            # Main Charts
            html.Div([
                # Area vs Frequency Chart
                html.Div([
                    dcc.Graph(id='area-frequency-chart')
                ], className='six columns'),

                # Timing Analysis Chart
                html.Div([
                    dcc.Graph(id='timing-analysis-chart')
                ], className='six columns')
            ], className='row', style={'marginBottom': '30px'}),

            # Secondary Charts
            html.Div([
                # Configuration Comparison
                html.Div([
                    dcc.Graph(id='config-comparison-chart')
                ], className='six columns'),

                # Synthesis Time Trends
                html.Div([
                    dcc.Graph(id='time-trends-chart')
                ], className='six columns')
            ], className='row', style={'marginBottom': '30px'}),

            # Detailed Data Table
            html.Div([
                html.H3("📋 Detailed Results", style={'color': '#2c3e50'}),
                html.Div(id='results-table')
            ], style={'marginTop': '40px'}),

            # Auto-refresh interval component
            dcc.Interval(
                id='interval-component',
                interval=30*1000,  # Update every 30 seconds
                n_intervals=0
            )
        ])

    def _setup_callbacks(self):
        """Setup dashboard callbacks for interactivity"""

        # Callback to populate sweep selector options
        @self.app.callback(
            Output('sweep-selector', 'options'),
            [Input('interval-component', 'n_intervals')]
        )
        def update_sweep_options(n_intervals):
            from synthesis_dashboard import WallySynthesisDashboard
            dashboard = WallySynthesisDashboard(self.results_dir)
            sweep_folders = dashboard.discover_sweep_folders()

            options = [{'label': sweep['display_name'], 'value': sweep['path']}
                      for sweep in sweep_folders]
            return options

        # Callback to show sweep information
        @self.app.callback(
            Output('sweep-info', 'children'),
            [Input('sweep-selector', 'value')]
        )
        def display_sweep_info(selected_sweep):
            if not selected_sweep:
                return html.Div([
                    html.I("ⓘ Using all recent synthesis data from the past week.",
                           style={'color': '#6c757d', 'fontSize': '14px'})
                ])

            try:
                from synthesis_dashboard import WallySynthesisDashboard
                dashboard = WallySynthesisDashboard(self.results_dir)
                _, sweep_metadata = dashboard.load_sweep_data(selected_sweep)

                return html.Div([
                    html.P([
                        html.Strong("Sweep Type: "), sweep_metadata['sweep_type'], html.Br(),
                        html.Strong("Runs: "), f"{sweep_metadata['successful_runs']}/{sweep_metadata['total_runs']}", html.Br(),
                        html.Strong("Frequency Range: "),
                        f"{sweep_metadata['frequency_range']['min']}-{sweep_metadata['frequency_range']['max']} MHz", html.Br(),
                        html.Strong("Configurations: "), ", ".join(sweep_metadata['configurations']), html.Br(),
                        html.Strong("Machine: "), sweep_metadata.get('machine', 'unknown'), html.Br(),
                        html.Strong("Date: "), sweep_metadata.get('timestamp', 'unknown')[:16]
                    ], style={'fontSize': '14px', 'color': '#495057'})
                ])
            except Exception as e:
                return html.Div([
                    html.P(f"⚠️ Error loading sweep info: {e!s}",
                           style={'color': '#dc3545', 'fontSize': '14px'})
                ])

        @self.app.callback(
            [Output('summary-cards', 'children'),
             Output('area-frequency-chart', 'figure'),
             Output('timing-analysis-chart', 'figure'),
             Output('config-comparison-chart', 'figure'),
             Output('time-trends-chart', 'figure'),
             Output('results-table', 'children')],
            [Input('config-filter', 'value'),
             Input('tech-filter', 'value'),
             Input('time-filter', 'value'),
             Input('sweep-selector', 'value'),
             Input('refresh-button', 'n_clicks'),
             Input('interval-component', 'n_intervals')]
        )
        def update_dashboard(config_filter, tech_filter, time_days, selected_sweep, refresh_clicks, n_intervals):
            # Load fresh data - either from specific sweep or all recent data
            if selected_sweep:
                try:
                    from synthesis_dashboard import WallySynthesisDashboard
                    dashboard = WallySynthesisDashboard(self.results_dir)
                    metrics, _ = dashboard.load_sweep_data(selected_sweep)
                    # Apply additional filters
                    metrics = self._apply_filters(metrics, config_filter, tech_filter)
                except Exception as e:
                    print(f"Error loading sweep data: {e}")
                    metrics = self._load_filtered_data(config_filter, tech_filter, time_days)
            else:
                metrics = self._load_filtered_data(config_filter, tech_filter, time_days)

            # Generate components
            summary_cards = self._create_summary_cards(metrics)
            area_freq_fig = self._create_area_frequency_chart(metrics)
            timing_fig = self._create_timing_analysis_chart(metrics)
            config_comp_fig = self._create_config_comparison_chart(metrics)
            time_trends_fig = self._create_time_trends_chart(metrics)
            results_table = self._create_results_table(metrics)

            return summary_cards, area_freq_fig, timing_fig, config_comp_fig, time_trends_fig, results_table

        # CSV Download callback
        @self.app.callback(
            Output("download-dataframe-csv", "data"),
            [Input("csv-download-button", "n_clicks")],
            [State('config-filter', 'value'),
             State('tech-filter', 'value'),
             State('time-filter', 'value'),
             State('sweep-selector', 'value')]
        )
        def download_csv(n_clicks, config_filter, tech_filter, time_days, selected_sweep):
            if not n_clicks:
                return dash.no_update

            # Load the same filtered data as the dashboard
            if selected_sweep:
                try:
                    from synthesis_dashboard import WallySynthesisDashboard
                    dashboard = WallySynthesisDashboard(self.results_dir)
                    metrics, _ = dashboard.load_sweep_data(selected_sweep)
                    metrics = self._apply_filters(metrics, config_filter, tech_filter)
                    filename_prefix = f"sweep_{Path(selected_sweep).name}"
                except Exception:
                    metrics = self._load_filtered_data(config_filter, tech_filter, time_days)
                    filename_prefix = "synthesis_data"
            else:
                metrics = self._load_filtered_data(config_filter, tech_filter, time_days)
                filename_prefix = "synthesis_data"

            # Convert to DataFrame
            df = self._metrics_to_dataframe(metrics)

            # Generate filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{filename_prefix}_{timestamp}.csv"

            return dcc.send_data_frame(df.to_csv, filename, index=False)

    def _load_filtered_data(self, config_filter, tech_filter, time_days):
        """Load and filter synthesis data"""
        # Check if we need to refresh data
        now = datetime.now()
        if (now - self.last_refresh).seconds > self.refresh_interval:
            self.data_cache.clear()
            self.last_refresh = now

        # Load metrics
        metrics = self.dashboard.load_metrics(self.dashboard.discover_result_files(time_days))

        # Apply filters
        if config_filter != 'all' and config_filter:
            if isinstance(config_filter, str):
                config_filter = [config_filter]
            metrics = [m for m in metrics if m.config in config_filter]

        if tech_filter != 'all' and tech_filter:
            if isinstance(tech_filter, str):
                tech_filter = [tech_filter]
            metrics = [m for m in metrics if m.technology in tech_filter]

        return metrics

    def _apply_filters(self, metrics, config_filter, tech_filter):
        """Apply configuration and technology filters to metrics"""
        # Apply config filter
        if config_filter != 'all' and config_filter:
            if isinstance(config_filter, str):
                config_filter = [config_filter]
            metrics = [m for m in metrics if m.config in config_filter]

        # Apply technology filter
        if tech_filter != 'all' and tech_filter:
            if isinstance(tech_filter, str):
                tech_filter = [tech_filter]
            metrics = [m for m in metrics if m.technology in tech_filter]

        return metrics

    def _metrics_to_dataframe(self, metrics):
        """Convert synthesis metrics to pandas DataFrame for CSV export"""
        if not metrics:
            return pd.DataFrame()

        data = []
        for metric in metrics:
            row = {
                'timestamp': metric.timestamp.strftime('%Y-%m-%d %H:%M:%S') if metric.timestamp else '',
                'config': metric.config,
                'technology': metric.technology,
                'frequency_mhz': metric.frequency_mhz,
                'success': metric.success,
                'area_um2': metric.area_um2 if metric.area_um2 is not None else '',
                'slack_ns': metric.slack_ns if metric.slack_ns is not None else '',
                'power_mw': metric.power_mw if metric.power_mw is not None else '',
                'cell_count': metric.cell_count if metric.cell_count is not None else '',
                'synthesis_time_s': metric.synthesis_time_s if metric.synthesis_time_s is not None else '',
                'critical_path_ns': getattr(metric, 'critical_path_ns', '') if hasattr(metric, 'critical_path_ns') else '',
                'run_type': metric.run_type,
                'git_hash': metric.git_hash if hasattr(metric, 'git_hash') else '',
                'machine': metric.machine if hasattr(metric, 'machine') else ''
            }
            data.append(row)

        df = pd.DataFrame(data)

        # Sort by timestamp and frequency for better organization
        if not df.empty:
            if 'timestamp' in df.columns:
                df = df.sort_values(['timestamp', 'frequency_mhz'], ascending=[False, True])
            else:
                df = df.sort_values('frequency_mhz', ascending=True)

        return df

    def _create_summary_cards(self, metrics):
        """Create summary statistics cards"""
        if not metrics:
            return html.Div("No data available", style={'textAlign': 'center', 'color': '#7f8c8d'})

        successful = [m for m in metrics if m.success]
        total_runs = len(metrics)
        success_rate = len(successful) / total_runs * 100 if total_runs > 0 else 0

        # Calculate statistics
        areas = [m.area_um2 for m in successful if m.area_um2 is not None]
        avg_area = sum(areas) / len(areas) if areas else 0

        slacks = [m.slack_ns for m in successful if m.slack_ns is not None]
        violations = sum(1 for s in slacks if s < 0)

        # Create cards
        cards = html.Div([
            # Total Runs Card
            html.Div([
                html.H3(f"{total_runs}", style={'color': '#3498db', 'margin': '0'}),
                html.P("Total Runs", style={'margin': '5px 0'})
            ], className='three columns', style={
                'textAlign': 'center', 'padding': '20px', 'backgroundColor': '#ffffff',
                'borderRadius': '10px', 'boxShadow': '0 2px 10px rgba(0,0,0,0.1)',
                'margin': '10px'
            }),

            # Success Rate Card
            html.Div([
                html.H3(f"{success_rate:.1f}%", style={'color': '#27ae60' if success_rate > 90 else '#f39c12', 'margin': '0'}),
                html.P("Success Rate", style={'margin': '5px 0'})
            ], className='three columns', style={
                'textAlign': 'center', 'padding': '20px', 'backgroundColor': '#ffffff',
                'borderRadius': '10px', 'boxShadow': '0 2px 10px rgba(0,0,0,0.1)',
                'margin': '10px'
            }),

            # Average Area Card
            html.Div([
                html.H3(f"{avg_area:,.0f} µm²", style={'color': '#9b59b6', 'margin': '0'}),
                html.P("Average Area", style={'margin': '5px 0'})
            ], className='three columns', style={
                'textAlign': 'center', 'padding': '20px', 'backgroundColor': '#ffffff',
                'borderRadius': '10px', 'boxShadow': '0 2px 10px rgba(0,0,0,0.1)',
                'margin': '10px'
            }),

            # Timing Violations Card
            html.Div([
                html.H3(f"{violations}", style={'color': '#e74c3c' if violations > 0 else '#27ae60', 'margin': '0'}),
                html.P("Timing Violations", style={'margin': '5px 0'})
            ], className='three columns', style={
                'textAlign': 'center', 'padding': '20px', 'backgroundColor': '#ffffff',
                'borderRadius': '10px', 'boxShadow': '0 2px 10px rgba(0,0,0,0.1)',
                'margin': '10px'
            })
        ], className='row')

        return cards

    def _create_area_frequency_chart(self, metrics):
        """Create interactive area vs frequency scatter plot"""
        if not metrics:
            return go.Figure().add_annotation(
                text="No data available", x=0.5, y=0.5, showarrow=False
            )

        # Filter to successful runs with area data
        valid_metrics = [m for m in metrics if m.success and m.area_um2 is not None]

        if not valid_metrics:
            return go.Figure().add_annotation(
                text="No valid area data", x=0.5, y=0.5, showarrow=False
            )

        # Create DataFrame for easier plotting
        df = pd.DataFrame([{
            'config': m.config,
            'frequency_mhz': m.frequency_mhz,
            'area_um2': m.area_um2,
            'technology': m.technology,
            'run_type': m.run_type,
            'timestamp': m.timestamp.strftime('%Y-%m-%d %H:%M')
        } for m in valid_metrics])

        # Create scatter plot
        fig = px.scatter(
            df, x='frequency_mhz', y='area_um2', color='config',
            hover_data=['technology', 'run_type', 'timestamp'],
            title='Area vs. Operating Frequency',
            labels={'frequency_mhz': 'Frequency (MHz)', 'area_um2': 'Area (µm²)'}
        )

        fig.update_layout(
            hovermode='closest',
            template='plotly_white',
            height=400
        )

        return fig

    def _create_timing_analysis_chart(self, metrics):
        """Create timing slack analysis chart"""
        if not metrics:
            return go.Figure().add_annotation(
                text="No data available", x=0.5, y=0.5, showarrow=False
            )

        # Filter to runs with timing data
        valid_metrics = [m for m in metrics if m.success and m.slack_ns is not None]

        if not valid_metrics:
            return go.Figure().add_annotation(
                text="No valid timing data", x=0.5, y=0.5, showarrow=False
            )

        slacks = [m.slack_ns for m in valid_metrics]

        # Create histogram
        fig = go.Figure(data=[
            go.Histogram(x=slacks, nbinsx=30, name='Slack Distribution')
        ])

        # Add timing failure line
        fig.add_vline(x=0, line_dash="dash", line_color="red",
                     annotation_text="Timing Failure", annotation_position="top")

        fig.update_layout(
            title='Timing Slack Distribution',
            xaxis_title='Slack (ns)',
            yaxis_title='Count',
            template='plotly_white',
            height=400
        )

        return fig

    def _create_config_comparison_chart(self, metrics):
        """Create configuration comparison bar chart"""
        if not metrics:
            return go.Figure().add_annotation(
                text="No data available", x=0.5, y=0.5, showarrow=False
            )

        # Group by configuration and calculate statistics
        config_stats = {}
        for m in metrics:
            if not m.success or m.area_um2 is None:
                continue

            if m.config not in config_stats:
                config_stats[m.config] = []
            config_stats[m.config].append(m.area_um2)

        if not config_stats:
            return go.Figure().add_annotation(
                text="No valid comparison data", x=0.5, y=0.5, showarrow=False
            )

        # Calculate means and std devs
        configs = list(config_stats.keys())
        means = [np.mean(config_stats[config]) for config in configs]
        stds = [np.std(config_stats[config]) if len(config_stats[config]) > 1 else 0
                for config in configs]

        # Create bar chart
        fig = go.Figure(data=[
            go.Bar(x=configs, y=means, error_y=dict(type='data', array=stds),
                   name='Average Area')
        ])

        fig.update_layout(
            title='Configuration Area Comparison',
            xaxis_title='Configuration',
            yaxis_title='Area (µm²)',
            template='plotly_white',
            height=400
        )

        return fig

    def _create_time_trends_chart(self, metrics):
        """Create synthesis time trends chart"""
        if not metrics:
            return go.Figure().add_annotation(
                text="No data available", x=0.5, y=0.5, showarrow=False
            )

        # Create DataFrame
        df = pd.DataFrame([{
            'timestamp': m.timestamp,
            'synthesis_time_s': m.synthesis_time_s,
            'config': m.config,
            'success': m.success
        } for m in metrics if m.synthesis_time_s is not None])

        if df.empty:
            return go.Figure().add_annotation(
                text="No synthesis time data", x=0.5, y=0.5, showarrow=False
            )

        # Sort by timestamp
        df = df.sort_values('timestamp')

        # Create line chart
        fig = px.line(
            df, x='timestamp', y='synthesis_time_s', color='config',
            title='Synthesis Time Trends',
            labels={'timestamp': 'Time', 'synthesis_time_s': 'Synthesis Time (s)'}
        )

        fig.update_layout(
            template='plotly_white',
            height=400
        )

        return fig

    def _create_results_table(self, metrics):
        """Create detailed results table with export capabilities"""
        if not metrics:
            return html.Div("No data available", style={'textAlign': 'center', 'padding': '20px'})

        # Convert to DataFrame for better table handling
        df = self._metrics_to_dataframe(metrics)

        if df.empty:
            return html.Div("No data available", style={'textAlign': 'center', 'padding': '20px'})

        # Format columns for display
        display_columns = [
            {'name': 'Timestamp', 'id': 'timestamp', 'type': 'text'},
            {'name': 'Config', 'id': 'config', 'type': 'text'},
            {'name': 'Tech', 'id': 'technology', 'type': 'text'},
            {'name': 'Freq (MHz)', 'id': 'frequency_mhz', 'type': 'numeric'},
            {'name': 'Area (µm²)', 'id': 'area_um2', 'type': 'numeric', 'format': {'specifier': ',.0f'}},
            {'name': 'Slack (ns)', 'id': 'slack_ns', 'type': 'numeric', 'format': {'specifier': '.3f'}},
            {'name': 'Power (mW)', 'id': 'power_mw', 'type': 'numeric', 'format': {'specifier': '.2f'}},
            {'name': 'Cells', 'id': 'cell_count', 'type': 'numeric'},
            {'name': 'Time (s)', 'id': 'synthesis_time_s', 'type': 'numeric', 'format': {'specifier': '.1f'}},
            {'name': 'Success', 'id': 'success', 'type': 'text'},
            {'name': 'Type', 'id': 'run_type', 'type': 'text'}
        ]

        # Create DataTable with export functionality

        table = dash_table.DataTable(
            data=df.to_dict('records'),
            columns=display_columns,
            style_table={'overflowX': 'auto'},
            style_header={
                'backgroundColor': '#3498db',
                'color': 'white',
                'fontWeight': 'bold',
                'textAlign': 'center'
            },
            style_cell={
                'textAlign': 'center',
                'padding': '10px',
                'fontSize': '14px',
                'fontFamily': 'Arial'
            },
            style_data_conditional=[
                {
                    'if': {'filter_query': '{success} = True'},
                    'backgroundColor': '#d5f4e6',
                    'color': 'black',
                },
                {
                    'if': {'filter_query': '{success} = False'},
                    'backgroundColor': '#f8d7da',
                    'color': 'black',
                }
            ],
            sort_action="native",
            filter_action="native",
            page_size=20,
            export_format="csv",
            export_headers="display"
        )

        return html.Div([
            html.H4("📊 Synthesis Results Table", style={'marginBottom': '15px'}),
            html.P("💡 Tip: Click column headers to sort, use the export button above to download as CSV",
                   style={'fontSize': '12px', 'color': '#7f8c8d', 'marginBottom': '10px'}),
            table
        ])

    def run(self, debug=False, host='0.0.0.0'):
        """Run the dashboard server"""
        print(f"🚀 Starting Wally Interactive Dashboard on http://localhost:{self.port}")
        print("📊 Dashboard features:")
        print("  • Real-time data refresh every 30 seconds")
        print("  • Interactive filtering by configuration and technology")
        print("  • Drill-down capabilities with hover details")
        print("  • Publication-quality plots")
        print("  • Responsive design")
        print()
        print("Access the dashboard in your web browser!")

        self.app.run(debug=debug, host=host, port=self.port)


def main():
    """Launch the interactive dashboard"""
    dashboard = WallyInteractiveDashboard()
    dashboard.run(debug=True)


if __name__ == '__main__':
    main()
