import os
import streamlit as st
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
import logging
from typing import List

class EmailService:
    def __init__(self, smtp_server=None, smtp_port=None, username=None, password=None):
        try:
            # Tenta usar parâmetros passados
            self.smtp_server = smtp_server or "smtp.gmail.com"
            self.smtp_port = smtp_port or 587
            
            # Tenta pegar credenciais do ambiente
            self.username = username or os.getenv('EMAIL_USERNAME')
            self.password = password or os.getenv('EMAIL_PASSWORD')
            
            # Se não encontrar, tenta das secrets
            if not self.username or not self.password:
                self.username = st.secrets["email"]["username"]
                self.password = st.secrets["email"]["password"]
                
        except Exception as e:
            raise ValueError("Credenciais de email precisam estar configuradas nas variáveis de ambiente ou nas secrets do Streamlit")
    
    def enviar_relatorio(self, destinatarios: List[str], arquivo_relatorio: str, assunto: str = None):
        """Envia relatório por e-mail"""
        try:
            msg = MIMEMultipart()
            msg['From'] = self.username
            msg['To'] = ', '.join(destinatarios)
            msg['Subject'] = assunto or 'Relatório de Impedimentos'
            
            # Corpo do e-mail
            corpo = """
            Segue em anexo o relatório de impedimentos gerado automaticamente.
            
            Este é um e-mail automático, por favor não responda.
            """
            msg.attach(MIMEText(corpo, 'plain'))
            
            # Anexa o relatório
            with open(arquivo_relatorio, 'rb') as f:
                part = MIMEApplication(f.read(), Name=arquivo_relatorio)
                part['Content-Disposition'] = f'attachment; filename="{arquivo_relatorio}"'
                msg.attach(part)
            
            # Envia o e-mail
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.username, self.password)
                server.send_message(msg)
                
            return True
            
        except Exception as e:
            logging.error(f"Erro ao enviar e-mail: {str(e)}")
            return False 