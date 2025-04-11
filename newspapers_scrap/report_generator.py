import os
import json
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
from pathlib import Path

logger = logging.getLogger(__name__)

class ScrapingReportGenerator:
    """Generate visual reports from scraping performance data"""
    
    def __init__(self, output_dir: Optional[str] = None):
        """
        Initialize the report generator
        
        Args:
            output_dir: Directory to save reports (default: reports/figures)
        """
        if output_dir:
            self.output_dir = Path(output_dir)
        else:
            self.output_dir = Path("reports/figures")
        
        # Create directory if it doesn't exist
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Set default style
        sns.set_theme(style="whitegrid")
        
        logger.info(f"Report generator initialized with output directory: {self.output_dir}")
    
    def generate_report(self, performance_data: Dict[str, Any], query: str = None) -> str:
        """
        Generate a comprehensive visual report from performance data
        
        Args:
            performance_data: Performance data dictionary from PerformanceTracker
            query: The search query used (optional)
            
        Returns:
            Path to the generated report directory
        """
        try:
            # Create a directory for this report based on query
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # Use query for report name if available, otherwise use timestamp
            if query:
                # Clean query for filename
                clean_query = "".join(c if c.isalnum() else "_" for c in query)
                report_name = f"scraping_report_{clean_query}"
            else:
                report_name = f"scraping_report_{timestamp}"
            
            # Check if directory already exists, if so, use it instead of creating a new one
            report_dir = self.output_dir / report_name
            
            # If directory exists, we'll update the existing report
            if report_dir.exists():
                logger.info(f"Updating existing report in {report_dir}")
            else:
                report_dir.mkdir(exist_ok=True)
                logger.info(f"Creating new report in {report_dir}")
            
            logger.info(f"Generating report in {report_dir}")
            
            # Save raw data as JSON
            try:
                with open(report_dir / "performance_data.json", "w", encoding="utf-8") as f:
                    json.dump(performance_data, f, indent=2, ensure_ascii=False)
            except Exception as e:
                logger.error(f"Error saving performance data as JSON: {e}")
            
            # Validate performance data structure
            self._validate_performance_data(performance_data)
            
            # Generate individual charts
            self._generate_time_distribution_chart(performance_data, report_dir)
            self._generate_articles_by_year_chart(performance_data, report_dir)
            self._generate_articles_by_newspaper_chart(performance_data, report_dir)
            self._generate_articles_by_canton_chart(performance_data, report_dir)
            self._generate_performance_metrics_chart(performance_data, report_dir)
            
            # Generate summary HTML
            self._generate_html_report(performance_data, report_dir, query)
            
            logger.info(f"Report generation complete: {report_dir}")
            return str(report_dir)
        except Exception as e:
            logger.error(f"Error generating report: {e}")
            # Create a minimal error report
            try:
                error_report_dir = self.output_dir / f"error_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                error_report_dir.mkdir(exist_ok=True)
                
                with open(error_report_dir / "error.txt", "w", encoding="utf-8") as f:
                    f.write(f"Error generating report: {str(e)}\n\n")
                    f.write(f"Query: {query}\n\n")
                    f.write("Performance data structure:\n")
                    f.write(str(performance_data))
                
                # Create a simple HTML error page
                with open(error_report_dir / "report.html", "w", encoding="utf-8") as f:
                    f.write(f"""
                    <!DOCTYPE html>
                    <html>
                    <head>
                        <title>Erreur de génération de rapport</title>
                        <style>
                            body {{ font-family: Arial, sans-serif; padding: 20px; }}
                            .error {{ color: red; background: #ffeeee; padding: 10px; border-radius: 5px; }}
                        </style>
                    </head>
                    <body>
                        <h1>Erreur lors de la génération du rapport</h1>
                        <div class="error">
                            <p><strong>Erreur:</strong> {str(e)}</p>
                        </div>
                        <p>Une erreur s'est produite lors de la génération du rapport. Veuillez vérifier les logs pour plus de détails.</p>
                        <p><strong>Requête:</strong> {query or 'Non spécifiée'}</p>
                        <p>Timestamp: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}</p>
                    </body>
                    </html>
                    """)
                
                return str(error_report_dir)
            except Exception as inner_e:
                logger.error(f"Failed to create error report: {inner_e}")
                return "Error generating report"
    
    def _generate_time_distribution_chart(self, data: Dict[str, Any], report_dir: Path):
        """Generate chart showing time distribution between different activities"""
        try:
            # Extract time data
            request_time = max(0, data['request_stats']['total_time'])
            delay_time = max(0, data['delay_stats']['total_time'])
            processing_time = max(0, data['processing_stats']['total_time'])
            
            # Ensure other_time is not negative
            total_time = data['total_time']
            tracked_time = request_time + delay_time + processing_time
            other_time = max(0, total_time - tracked_time)
            
            # Create data for pie chart
            labels = ['Requêtes', 'Délais', 'Traitement', 'Autre']
            sizes = [request_time, delay_time, processing_time, other_time]
            
            # Ensure we have at least some data to show
            if sum(sizes) <= 0:
                logger.warning("No time data available for pie chart, using placeholder values")
                sizes = [1, 1, 1, 1]  # Placeholder equal values
            
            # Create pie chart with a new figure to avoid thread issues
            fig, ax = plt.subplots(figsize=(10, 7))
            ax.pie(sizes, labels=labels, autopct='%1.1f%%', startangle=90, 
                   colors=sns.color_palette("viridis", 4))
            ax.axis('equal')
            ax.set_title('Distribution du temps total de scraping')
            
            # Save figure and explicitly close it
            fig.savefig(report_dir / "time_distribution.png", dpi=300, bbox_inches='tight')
            plt.close(fig)
            
            logger.info("Generated time distribution chart")
        except Exception as e:
            logger.error(f"Error generating time distribution chart: {e}")
            # Create a fallback image in case of error
            try:
                fig, ax = plt.subplots(figsize=(10, 7))
                ax.text(0.5, 0.5, 'Erreur lors de la génération du graphique', 
                        horizontalalignment='center', verticalalignment='center',
                        fontsize=14, color='red')
                fig.savefig(report_dir / "time_distribution.png", dpi=300, bbox_inches='tight')
                plt.close(fig)
            except Exception as inner_e:
                logger.error(f"Failed to create fallback chart: {inner_e}")
    
    def _generate_articles_by_year_chart(self, data: Dict[str, Any], report_dir: Path):
        """Generate chart showing articles by year"""
        try:
            articles_by_year = data['articles_per_year']
            if not articles_by_year:
                logger.warning("No article year data available for chart")
                # Create a placeholder chart
                fig, ax = plt.subplots(figsize=(12, 6))
                ax.text(0.5, 0.5, 'Aucune donnée disponible par année', 
                         horizontalalignment='center', verticalalignment='center',
                         fontsize=14)
                fig.tight_layout()
                fig.savefig(report_dir / "articles_by_year.png", dpi=300, bbox_inches='tight')
                plt.close(fig)
                return
                
            # Convert to DataFrame for easier plotting
            df = pd.DataFrame(list(articles_by_year.items()), columns=['Année', 'Nombre d\'articles'])
            df = df.sort_values('Année')
            
            fig, ax = plt.subplots(figsize=(12, 6))
            sns.barplot(x='Année', y='Nombre d\'articles', data=df, ax=ax)
            ax.set_title('Articles par année')
            ax.set_xticklabels(ax.get_xticklabels(), rotation=45)
            
            # Add value labels on top of bars
            for i, v in enumerate(df['Nombre d\'articles']):
                ax.text(i, v + 0.1, str(v), ha='center')
            
            fig.tight_layout()
            fig.savefig(report_dir / "articles_by_year.png", dpi=300, bbox_inches='tight')
            plt.close(fig)
            
            logger.info("Generated articles by year chart")
        except Exception as e:
            logger.error(f"Error generating articles by year chart: {e}")
            # Create a fallback chart
            try:
                fig, ax = plt.subplots(figsize=(12, 6))
                ax.text(0.5, 0.5, 'Erreur lors de la génération du graphique', 
                         horizontalalignment='center', verticalalignment='center',
                         fontsize=14, color='red')
                fig.tight_layout()
                fig.savefig(report_dir / "articles_by_year.png", dpi=300, bbox_inches='tight')
                plt.close(fig)
            except Exception as inner_e:
                logger.error(f"Failed to create fallback chart: {inner_e}")
    
    def _generate_articles_by_newspaper_chart(self, data: Dict[str, Any], report_dir: Path):
        """Generate chart showing articles by newspaper"""
        try:
            articles_by_newspaper = data['articles_per_newspaper']
            if not articles_by_newspaper:
                logger.warning("No newspaper data available for chart")
                # Create a placeholder chart
                fig, ax = plt.subplots(figsize=(12, 6))
                ax.text(0.5, 0.5, 'Aucune donnée disponible par journal', 
                         horizontalalignment='center', verticalalignment='center',
                         fontsize=14)
                fig.tight_layout()
                fig.savefig(report_dir / "articles_by_newspaper.png", dpi=300, bbox_inches='tight')
                plt.close(fig)
                return
                
            # Convert to DataFrame and sort by count
            df = pd.DataFrame(list(articles_by_newspaper.items()), 
                             columns=['Journal', 'Nombre d\'articles'])
            df = df.sort_values('Nombre d\'articles', ascending=False)
            
            # Limit to top 10 if there are many newspapers
            if len(df) > 10:
                df = df.head(10)
                title = 'Top 10 des journaux par nombre d\'articles'
            else:
                title = 'Articles par journal'
            
            fig, ax = plt.subplots(figsize=(12, 6))
            sns.barplot(x='Nombre d\'articles', y='Journal', data=df, ax=ax)
            ax.set_title(title)
            
            # Add value labels
            for i, v in enumerate(df['Nombre d\'articles']):
                # Ensure we don't place text too far if value is very small
                offset = max(0.1, v * 0.05) if v > 0 else 0.1
                ax.text(v + offset, i, str(v), va='center')
            
            fig.tight_layout()
            fig.savefig(report_dir / "articles_by_newspaper.png", dpi=300, bbox_inches='tight')
            plt.close(fig)
            
            logger.info("Generated articles by newspaper chart")
        except Exception as e:
            logger.error(f"Error generating articles by newspaper chart: {e}")
            # Create a fallback chart
            try:
                fig, ax = plt.subplots(figsize=(12, 6))
                ax.text(0.5, 0.5, 'Erreur lors de la génération du graphique', 
                         horizontalalignment='center', verticalalignment='center',
                         fontsize=14, color='red')
                fig.tight_layout()
                fig.savefig(report_dir / "articles_by_newspaper.png", dpi=300, bbox_inches='tight')
                plt.close(fig)
            except Exception as inner_e:
                logger.error(f"Failed to create fallback chart: {inner_e}")
    
    def _generate_articles_by_canton_chart(self, data: Dict[str, Any], report_dir: Path):
        """Generate chart showing articles by canton"""
        try:
            articles_by_canton = data['articles_per_canton']
            if not articles_by_canton:
                logger.warning("No canton data available for chart")
                # Create a placeholder chart
                fig, ax = plt.subplots(figsize=(12, 6))
                ax.text(0.5, 0.5, 'Aucune donnée disponible par canton', 
                         horizontalalignment='center', verticalalignment='center',
                         fontsize=14)
                fig.tight_layout()
                fig.savefig(report_dir / "articles_by_canton.png", dpi=300, bbox_inches='tight')
                plt.close(fig)
                return
                
            # Convert to DataFrame and sort by count
            df = pd.DataFrame(list(articles_by_canton.items()), 
                             columns=['Canton', 'Nombre d\'articles'])
            df = df.sort_values('Nombre d\'articles', ascending=False)
            
            fig, ax = plt.subplots(figsize=(12, 6))
            sns.barplot(x='Nombre d\'articles', y='Canton', data=df, ax=ax)
            ax.set_title('Articles par canton')
            
            # Add value labels
            for i, v in enumerate(df['Nombre d\'articles']):
                # Ensure we don't place text too far if value is very small
                offset = max(0.1, v * 0.05) if v > 0 else 0.1
                ax.text(v + offset, i, str(v), va='center')
            
            fig.tight_layout()
            fig.savefig(report_dir / "articles_by_canton.png", dpi=300, bbox_inches='tight')
            plt.close(fig)
            
            logger.info("Generated articles by canton chart")
        except Exception as e:
            logger.error(f"Error generating articles by canton chart: {e}")
            # Create a fallback chart
            try:
                fig, ax = plt.subplots(figsize=(12, 6))
                ax.text(0.5, 0.5, 'Erreur lors de la génération du graphique', 
                         horizontalalignment='center', verticalalignment='center',
                         fontsize=14, color='red')
                fig.tight_layout()
                fig.savefig(report_dir / "articles_by_canton.png", dpi=300, bbox_inches='tight')
                plt.close(fig)
            except Exception as inner_e:
                logger.error(f"Failed to create fallback chart: {inner_e}")
    
    def _generate_performance_metrics_chart(self, data: Dict[str, Any], report_dir: Path):
        """Generate chart showing performance metrics"""
        try:
            # Extract performance metrics with safe defaults
            metrics = {
                'Articles par minute': max(0, data['performance_metrics']['articles_per_minute']),
                'Taux de succès (%)': max(0, data['performance_metrics']['success_rate']),
                'Temps moyen de requête (s)': max(0, data['request_stats']['average_time']),
                'Temps moyen de traitement (s)': max(0, data['processing_stats']['average_time']),
                'Temps moyen de délai (s)': max(0, data['delay_stats']['average_time'])
            }
            
            # Create DataFrame
            df = pd.DataFrame(list(metrics.items()), columns=['Métrique', 'Valeur'])
            
            # Create horizontal bar chart with explicit figure and axes
            fig, ax = plt.subplots(figsize=(12, 6))
            sns.barplot(x='Valeur', y='Métrique', data=df, ax=ax)
            ax.set_title('Métriques de performance')
            
            # Add value labels
            for i, v in enumerate(df['Valeur']):
                # Ensure we don't place text too far if value is very small
                offset = max(0.1, v * 0.05) if v > 0 else 0.1
                ax.text(v + offset, i, f"{v:.2f}", va='center')
            
            fig.tight_layout()
            fig.savefig(report_dir / "performance_metrics.png", dpi=300, bbox_inches='tight')
            plt.close(fig)
            
            logger.info("Generated performance metrics chart")
        except Exception as e:
            logger.error(f"Error generating performance metrics chart: {e}")
            # Create a fallback chart
            try:
                fig, ax = plt.subplots(figsize=(12, 6))
                ax.text(0.5, 0.5, 'Erreur lors de la génération du graphique', 
                         horizontalalignment='center', verticalalignment='center',
                         fontsize=14, color='red')
                fig.tight_layout()
                fig.savefig(report_dir / "performance_metrics.png", dpi=300, bbox_inches='tight')
                plt.close(fig)
            except Exception as inner_e:
                logger.error(f"Failed to create fallback chart: {inner_e}")
    
    def _validate_performance_data(self, data: Dict[str, Any]) -> None:
        """Validate and fix performance data structure to avoid errors"""
        # Ensure all required keys exist
        required_keys = ['total_time', 'total_articles', 'articles_per_year', 
                         'articles_per_newspaper', 'articles_per_canton', 
                         'search_terms', 'error_count', 'retry_count',
                         'request_stats', 'delay_stats', 'processing_stats',
                         'performance_metrics']
        
        for key in required_keys:
            if key not in data:
                logger.warning(f"Missing key in performance data: {key}")
                if key in ['articles_per_year', 'articles_per_newspaper', 'articles_per_canton', 'search_terms']:
                    data[key] = {}
                elif key in ['request_stats', 'delay_stats', 'processing_stats', 'performance_metrics']:
                    data[key] = {}
                else:
                    data[key] = 0
        
        # Ensure stats dictionaries have required fields
        for stats_key in ['request_stats', 'delay_stats', 'processing_stats']:
            if not isinstance(data[stats_key], dict):
                data[stats_key] = {}
            
            for field in ['count', 'total_time', 'average_time', 'min_time', 'max_time']:
                if field not in data[stats_key]:
                    data[stats_key][field] = 0
        
        # Ensure performance metrics have required fields
        if not isinstance(data['performance_metrics'], dict):
            data['performance_metrics'] = {}
        
        for field in ['articles_per_minute', 'success_rate']:
            if field not in data['performance_metrics']:
                data['performance_metrics'][field] = 0
        
        logger.info("Performance data validated and fixed if needed")

    def _generate_html_report(self, data: Dict[str, Any], report_dir: Path, query: Optional[str] = None):
        """Generate an HTML report that includes all charts and summary statistics"""
        try:
            # Format timestamp
            timestamp = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            
            # Calculate human-readable total time
            total_seconds = data['total_time']
            hours, remainder = divmod(total_seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            time_str = f"{int(hours)}h {int(minutes)}m {int(seconds)}s"
            
            # Create HTML content
            html_content = f"""
            <!DOCTYPE html>
            <html lang="fr">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Rapport de Scraping - {timestamp}</title>
                <style>
                    body {{
                        font-family: Arial, sans-serif;
                        line-height: 1.6;
                        color: #333;
                        max-width: 1200px;
                        margin: 0 auto;
                        padding: 20px;
                    }}
                    h1, h2, h3 {{
                        color: #2c3e50;
                    }}
                    .report-header {{
                        background-color: #f8f9fa;
                        padding: 20px;
                        border-radius: 5px;
                        margin-bottom: 30px;
                        border-left: 5px solid #3498db;
                    }}
                    .stats-container {{
                        display: flex;
                        flex-wrap: wrap;
                        gap: 20px;
                        margin-bottom: 30px;
                    }}
                    .stat-card {{
                        background-color: #fff;
                        border-radius: 5px;
                        padding: 15px;
                        box-shadow: 0 2px 5px rgba(0,0,0,0.1);
                        flex: 1;
                        min-width: 200px;
                    }}
                    .stat-value {{
                        font-size: 24px;
                        font-weight: bold;
                        color: #3498db;
                    }}
                    .stat-label {{
                        font-size: 14px;
                        color: #7f8c8d;
                    }}
                    .chart-container {{
                        margin-bottom: 40px;
                    }}
                    .chart-container img {{
                        max-width: 100%;
                        height: auto;
                        border-radius: 5px;
                        box-shadow: 0 3px 10px rgba(0,0,0,0.1);
                    }}
                    table {{
                        width: 100%;
                        border-collapse: collapse;
                        margin-bottom: 30px;
                    }}
                    th, td {{
                        padding: 12px 15px;
                        text-align: left;
                        border-bottom: 1px solid #ddd;
                    }}
                    th {{
                        background-color: #f2f2f2;
                    }}
                    tr:hover {{
                        background-color: #f5f5f5;
                    }}
                    .footer {{
                        margin-top: 50px;
                        padding-top: 20px;
                        border-top: 1px solid #eee;
                        font-size: 12px;
                        color: #7f8c8d;
                        text-align: center;
                    }}
                </style>
            </head>
            <body>
                <div class="report-header">
                    <h1>Rapport de Scraping</h1>
                    <p>Généré le {timestamp}</p>
                    {f'<p>Requête: <strong>{query}</strong></p>' if query else ''}
                </div>
                
                <div class="stats-container">
                    <div class="stat-card">
                        <div class="stat-value">{data['total_articles']}</div>
                        <div class="stat-label">Articles collectés</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value">{time_str}</div>
                        <div class="stat-label">Temps total</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value">{data['performance_metrics']['articles_per_minute']:.2f}</div>
                        <div class="stat-label">Articles par minute</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value">{data['performance_metrics']['success_rate']:.1f}%</div>
                        <div class="stat-label">Taux de succès</div>
                    </div>
                </div>
                
                <h2>Distribution du temps</h2>
                <div class="chart-container">
                    <img src="time_distribution.png" alt="Distribution du temps">
                </div>
                
                <h2>Articles par année</h2>
                <div class="chart-container">
                    <img src="articles_by_year.png" alt="Articles par année">
                </div>
                
                <h2>Articles par journal</h2>
                <div class="chart-container">
                    <img src="articles_by_newspaper.png" alt="Articles par journal">
                </div>
            """
            
            # Add canton chart if available
            if data['articles_per_canton']:
                html_content += """
                <h2>Articles par canton</h2>
                <div class="chart-container">
                    <img src="articles_by_canton.png" alt="Articles par canton">
                </div>
                """
            
            # Add performance metrics
            html_content += """
                <h2>Métriques de performance</h2>
                <div class="chart-container">
                    <img src="performance_metrics.png" alt="Métriques de performance">
                </div>
                
                <h2>Statistiques détaillées</h2>
                <table>
                    <tr>
                        <th>Métrique</th>
                        <th>Valeur</th>
                    </tr>
            """
            
            # Add request stats
            html_content += f"""
                    <tr>
                        <td>Nombre de requêtes</td>
                        <td>{data['request_stats']['count']}</td>
                    </tr>
                    <tr>
                        <td>Temps moyen de requête</td>
                        <td>{data['request_stats']['average_time']:.2f} secondes</td>
                    </tr>
                    <tr>
                        <td>Temps total de requête</td>
                        <td>{data['request_stats']['total_time']:.2f} secondes</td>
                    </tr>
                    <tr>
                        <td>Nombre d'erreurs</td>
                        <td>{data['error_count']}</td>
                    </tr>
                    <tr>
                        <td>Nombre de tentatives</td>
                        <td>{data['retry_count']}</td>
                    </tr>
            """
            
            # Add search terms if available
            if data['search_terms']:
                html_content += """
                    <tr>
                        <td>Termes de recherche</td>
                        <td>
                """
                for term in data['search_terms']:
                    html_content += f"<div>{term}</div>"
                html_content += """
                        </td>
                    </tr>
                """
            
            # Close table and HTML
            html_content += """
                </table>
                
                <div class="footer">
                    <p>Ce rapport a été généré automatiquement par le système de scraping de journaux.</p>
                </div>
            </body>
            </html>
            """
            
            # Write HTML to file
            with open(report_dir / "report.html", "w", encoding="utf-8") as f:
                f.write(html_content)
            
            logger.info(f"Generated HTML report at {report_dir / 'report.html'}")
        except Exception as e:
            logger.error(f"Error generating HTML report: {e}")
