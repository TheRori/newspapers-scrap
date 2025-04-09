import os
import json
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
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
        # Create a timestamped directory for this report
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_name = f"scraping_report_{timestamp}"
        if query:
            # Clean query for filename
            clean_query = "".join(c if c.isalnum() else "_" for c in query)
            report_name = f"scraping_report_{clean_query}_{timestamp}"
        
        report_dir = self.output_dir / report_name
        report_dir.mkdir(exist_ok=True)
        
        logger.info(f"Generating report in {report_dir}")
        
        # Save raw data as JSON
        with open(report_dir / "performance_data.json", "w", encoding="utf-8") as f:
            json.dump(performance_data, f, indent=2, ensure_ascii=False)
        
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
    
    def _generate_time_distribution_chart(self, data: Dict[str, Any], report_dir: Path):
        """Generate chart showing time distribution between different activities"""
        try:
            # Extract time data
            request_time = data['request_stats']['total_time']
            delay_time = data['delay_stats']['total_time']
            processing_time = data['processing_stats']['total_time']
            other_time = data['total_time'] - (request_time + delay_time + processing_time)
            
            # Create data for pie chart
            labels = ['Requêtes', 'Délais', 'Traitement', 'Autre']
            sizes = [request_time, delay_time, processing_time, other_time]
            
            # Create pie chart
            plt.figure(figsize=(10, 7))
            plt.pie(sizes, labels=labels, autopct='%1.1f%%', startangle=90, 
                   colors=sns.color_palette("viridis", 4))
            plt.axis('equal')
            plt.title('Distribution du temps total de scraping')
            
            # Save figure
            plt.savefig(report_dir / "time_distribution.png", dpi=300, bbox_inches='tight')
            plt.close()
            
            logger.info("Generated time distribution chart")
        except Exception as e:
            logger.error(f"Error generating time distribution chart: {e}")
    
    def _generate_articles_by_year_chart(self, data: Dict[str, Any], report_dir: Path):
        """Generate chart showing articles by year"""
        try:
            articles_by_year = data['articles_per_year']
            if not articles_by_year:
                logger.warning("No article year data available for chart")
                return
                
            # Convert to DataFrame for easier plotting
            df = pd.DataFrame(list(articles_by_year.items()), columns=['Année', 'Nombre d\'articles'])
            df = df.sort_values('Année')
            
            plt.figure(figsize=(12, 6))
            ax = sns.barplot(x='Année', y='Nombre d\'articles', data=df)
            plt.title('Articles par année')
            plt.xticks(rotation=45)
            
            # Add value labels on top of bars
            for i, v in enumerate(df['Nombre d\'articles']):
                ax.text(i, v + 0.1, str(v), ha='center')
            
            plt.tight_layout()
            plt.savefig(report_dir / "articles_by_year.png", dpi=300, bbox_inches='tight')
            plt.close()
            
            logger.info("Generated articles by year chart")
        except Exception as e:
            logger.error(f"Error generating articles by year chart: {e}")
    
    def _generate_articles_by_newspaper_chart(self, data: Dict[str, Any], report_dir: Path):
        """Generate chart showing articles by newspaper"""
        try:
            articles_by_newspaper = data['articles_per_newspaper']
            if not articles_by_newspaper:
                logger.warning("No newspaper data available for chart")
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
            
            plt.figure(figsize=(12, 6))
            ax = sns.barplot(x='Nombre d\'articles', y='Journal', data=df)
            plt.title(title)
            
            # Add value labels
            for i, v in enumerate(df['Nombre d\'articles']):
                ax.text(v + 0.1, i, str(v), va='center')
            
            plt.tight_layout()
            plt.savefig(report_dir / "articles_by_newspaper.png", dpi=300, bbox_inches='tight')
            plt.close()
            
            logger.info("Generated articles by newspaper chart")
        except Exception as e:
            logger.error(f"Error generating articles by newspaper chart: {e}")
    
    def _generate_articles_by_canton_chart(self, data: Dict[str, Any], report_dir: Path):
        """Generate chart showing articles by canton"""
        try:
            articles_by_canton = data['articles_per_canton']
            if not articles_by_canton:
                logger.warning("No canton data available for chart")
                return
                
            # Convert to DataFrame and sort by count
            df = pd.DataFrame(list(articles_by_canton.items()), 
                             columns=['Canton', 'Nombre d\'articles'])
            df = df.sort_values('Nombre d\'articles', ascending=False)
            
            plt.figure(figsize=(12, 6))
            ax = sns.barplot(x='Nombre d\'articles', y='Canton', data=df)
            plt.title('Articles par canton')
            
            # Add value labels
            for i, v in enumerate(df['Nombre d\'articles']):
                ax.text(v + 0.1, i, str(v), va='center')
            
            plt.tight_layout()
            plt.savefig(report_dir / "articles_by_canton.png", dpi=300, bbox_inches='tight')
            plt.close()
            
            logger.info("Generated articles by canton chart")
        except Exception as e:
            logger.error(f"Error generating articles by canton chart: {e}")
    
    def _generate_performance_metrics_chart(self, data: Dict[str, Any], report_dir: Path):
        """Generate chart showing performance metrics"""
        try:
            # Extract performance metrics
            metrics = {
                'Articles par minute': data['performance_metrics']['articles_per_minute'],
                'Taux de succès (%)': data['performance_metrics']['success_rate'],
                'Temps moyen de requête (s)': data['request_stats']['average_time'],
                'Temps moyen de traitement (s)': data['processing_stats']['average_time'],
                'Temps moyen de délai (s)': data['delay_stats']['average_time']
            }
            
            # Create DataFrame
            df = pd.DataFrame(list(metrics.items()), columns=['Métrique', 'Valeur'])
            
            # Create horizontal bar chart
            plt.figure(figsize=(12, 6))
            ax = sns.barplot(x='Valeur', y='Métrique', data=df)
            plt.title('Métriques de performance')
            
            # Add value labels
            for i, v in enumerate(df['Valeur']):
                ax.text(v + 0.1, i, f"{v:.2f}", va='center')
            
            plt.tight_layout()
            plt.savefig(report_dir / "performance_metrics.png", dpi=300, bbox_inches='tight')
            plt.close()
            
            logger.info("Generated performance metrics chart")
        except Exception as e:
            logger.error(f"Error generating performance metrics chart: {e}")
    
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
