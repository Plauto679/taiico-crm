import os
import datetime
import uuid
from pathlib import Path
from sqlalchemy import (
    create_engine, Column, String, Integer, Numeric, Boolean,
    DateTime, Date, ForeignKey, Text, JSON, UniqueConstraint
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent

# Load env file if it exists
load_dotenv(BACKEND_DIR / ".env")

# Database Connection URL (Postgres/AlloyDB in production, falls back to SQLite for local fallback)
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{BACKEND_DIR / 'taiico_local_fallback.db'}")

engine = create_engine(
    DATABASE_URL, 
    # Only use connect_args for sqlite to avoid thread safety errors during local dev
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    """Dependency helper to get a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# 1. User Model
class User(Base):
    __tablename__ = "users"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    role = Column(String(50), nullable=False) # management, broker, prospectador, cobranza, claims, recruiter, etc.
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    # Relationships
    clients = relationship("Client", back_populates="responsible_user")
    leads = relationship("Lead", back_populates="assigned_user")
    policies = relationship("Policy", back_populates="responsible_user")
    tasks = relationship("Task", back_populates="assigned_user")
    escalations = relationship("Escalation", back_populates="assigned_user")
    approvals_reviewed = relationship("HumanApproval", back_populates="reviewed_by_user")
    strategy_proposals = relationship("StrategyProposal", back_populates="approved_by_user")

# 2. Insurer Model
class Insurer(Base):
    __tablename__ = "insurers"
    
    id = Column(String(50), primary_key=True) # metlife, sura, aarco, axa
    name = Column(String(255), nullable=False)
    portal_url = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    products = relationship("Product", back_populates="insurer")
    policies = relationship("Policy", back_populates="insurer")

# 3. Product Model
class Product(Base):
    __tablename__ = "products"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    insurer_id = Column(String(50), ForeignKey("insurers.id"), nullable=False)
    name = Column(String(255), nullable=False)
    branch = Column(String(50), nullable=False) # VIDA, GMM, AUTOS, DANOS
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    insurer = relationship("Insurer", back_populates="products")
    policies = relationship("Policy", back_populates="product")
    leads = relationship("Lead", back_populates="product")

# 4. Client Model
class Client(Base):
    __tablename__ = "clients"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    full_name = Column(String(255), nullable=False)
    email = Column(String(255), unique=False, nullable=True) # Changed from unique=True to allow corporate and family shared emails
    phone = Column(String(50), nullable=True)
    responsible_user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    status = Column(String(50), default="active", nullable=False) # active, inactive
    communication_preference = Column(String(50), default="email")
    risk_profile = Column(String(50), default="low")
    metadata_json = Column("metadata", JSON, default={}) # Store wallet, relationships, notes
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    responsible_user = relationship("User", back_populates="clients")
    policies = relationship("Policy", back_populates="client")
    payments = relationship("Payment", back_populates="client")
    renewals = relationship("Renewal", back_populates="client")
    claims = relationship("Claim", back_populates="client")
    documents = relationship("Document", back_populates="client")
    conversations = relationship("Conversation", back_populates="client")

# 5. Lead Model
class Lead(Base):
    __tablename__ = "leads"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False)
    phone = Column(String(50), nullable=True)
    email = Column(String(255), nullable=True)
    interest_type = Column(String(50), default="unknown", nullable=False) # policy, agent_recruitment, unknown
    product_id = Column(String(36), ForeignKey("products.id"), nullable=True)
    source_channel = Column(String(100), nullable=True)
    urgency = Column(String(50), default="medium")
    pipeline_stage = Column(String(50), default="new", nullable=False) # new, contacted, qualified, etc.
    qualification_score = Column(Numeric(3, 2), default=0.00)
    assigned_user_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    metadata_json = Column("metadata", JSON, default={})
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    product = relationship("Product", back_populates="leads")
    assigned_user = relationship("User", back_populates="leads")
    candidate = relationship("Candidate", back_populates="lead", uselist=False)
    conversations = relationship("Conversation", back_populates="lead")

# 6. Policy Model
class Policy(Base):
    __tablename__ = "policies"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    policy_number = Column(String(100), unique=True, nullable=False)
    client_id = Column(String(36), ForeignKey("clients.id"), nullable=False)
    insurer_id = Column(String(50), ForeignKey("insurers.id"), nullable=False)
    product_id = Column(String(36), ForeignKey("products.id"), nullable=False)
    effective_start_date = Column(Date, nullable=False)
    effective_end_date = Column(Date, nullable=False)
    status = Column(String(50), default="in_force", nullable=False) # in_force, lapsed, cancelled, renewed
    premium_amount = Column(Numeric(12, 2), nullable=False)
    payment_frequency = Column(String(50), nullable=False) # monthly, quarterly, semi_annual, annual
    responsible_user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    document_link = Column(String(500), nullable=True)
    commission_percentage = Column(Numeric(5, 2), default=0.00, nullable=False)
    metadata_json = Column("metadata", JSON, default={})
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    client = relationship("Client", back_populates="policies")
    insurer = relationship("Insurer", back_populates="policies")
    product = relationship("Product", back_populates="policies")
    responsible_user = relationship("User", back_populates="policies")
    payments = relationship("Payment", back_populates="policy")
    renewals = relationship("Renewal", foreign_keys="[Renewal.original_policy_id]", back_populates="original_policy")
    claims = relationship("Claim", back_populates="policy")
    documents = relationship("Document", back_populates="policy")

# 7. Payment Model
class Payment(Base):
    __tablename__ = "payments"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    policy_id = Column(String(36), ForeignKey("policies.id"), nullable=False)
    client_id = Column(String(36), ForeignKey("clients.id"), nullable=False)
    expected_amount = Column(Numeric(12, 2), nullable=False)
    paid_amount = Column(Numeric(12, 2), default=0.00)
    due_date = Column(Date, nullable=False)
    received_date = Column(Date, nullable=True)
    status = Column(String(50), default="expected", nullable=False) # expected, paid, missing, late, partial, unconfirmed, etc.
    source_file = Column(String(255), nullable=True)
    grace_period_deadline = Column(Date, nullable=False)
    cancellation_risk_level = Column(String(50), default="none")
    evidence_document_id = Column(String(36), ForeignKey("documents.id"), nullable=True)
    reconciliation_confidence = Column(Numeric(3, 2), default=1.00)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    policy = relationship("Policy", back_populates="payments")
    client = relationship("Client", back_populates="payments")
    evidence_document = relationship("Document", foreign_keys=[evidence_document_id])

# 8. Renewal Model
class Renewal(Base):
    __tablename__ = "renewals"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    original_policy_id = Column(String(36), ForeignKey("policies.id"), nullable=False)
    client_id = Column(String(36), ForeignKey("clients.id"), nullable=False)
    status = Column(String(50), default="not_started", nullable=False) # not_started, approaching, in_progress, renewed, etc.
    renewal_deadline = Column(Date, nullable=False)
    renewal_quote_amount = Column(Numeric(12, 2), nullable=True)
    renewal_policy_id = Column(String(36), ForeignKey("policies.id"), nullable=True)
    requested_modifications = Column(JSON, default={})
    insurer_response = Column(Text, nullable=True)
    client_decision = Column(String(50), nullable=True) # accept, negotiate, reject
    risk_level = Column(String(50), default="none")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    original_policy = relationship("Policy", foreign_keys=[original_policy_id], back_populates="renewals")
    client = relationship("Client", back_populates="renewals")
    renewal_policy = relationship("Policy", foreign_keys=[renewal_policy_id])

# 9. Claim Model
class Claim(Base):
    __tablename__ = "claims"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    policy_id = Column(String(36), ForeignKey("policies.id"), nullable=False)
    client_id = Column(String(36), ForeignKey("clients.id"), nullable=False)
    claim_number = Column(String(100), nullable=True)
    status = Column(String(50), default="opened", nullable=False) # opened, documents_requested, etc.
    reported_date = Column(Date, nullable=False)
    resolution_date = Column(Date, nullable=True)
    escalation_level = Column(String(50), default="none")
    metadata_json = Column("metadata", JSON, default={})
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    policy = relationship("Policy", back_populates="claims")
    client = relationship("Client", back_populates="claims")
    documents = relationship("Document", back_populates="claim")

# 10. Document Model
class Document(Base):
    __tablename__ = "documents"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    google_drive_id = Column(String(255), unique=True, nullable=False)
    name = Column(String(255), nullable=False)
    file_type = Column(String(50), nullable=False) # pdf, xlsx, docx
    category = Column(String(100), nullable=False) # policy_pdf, payment_evidence, crm_export, etc.
    client_id = Column(String(36), ForeignKey("clients.id"), nullable=True)
    policy_id = Column(String(36), ForeignKey("policies.id"), nullable=True)
    claim_id = Column(String(36), ForeignKey("claims.id"), nullable=True)
    status = Column(String(50), default="uploaded", nullable=False) # uploaded, verified, rejected
    uploaded_by = Column(String(100), nullable=False) # Agent ID or User ID
    drive_link = Column(String(500), nullable=False)
    metadata_json = Column("metadata", JSON, default={})
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    client = relationship("Client", back_populates="documents")
    policy = relationship("Policy", back_populates="documents")
    claim = relationship("Claim", back_populates="documents")

# 11. Task Model
class Task(Base):
    __tablename__ = "tasks"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String(50), default="pending", nullable=False) # pending, completed, etc.
    priority = Column(String(50), default="medium", nullable=False) # low, medium, high, urgent
    assigned_agent = Column(String(100), nullable=True)
    assigned_user_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    related_entity_type = Column(String(50), nullable=True) # policy, client, payment, claim, renewal, lead
    related_entity_id = Column(String(36), nullable=True)
    due_date = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    assigned_user = relationship("User", back_populates="tasks")

# 12. Conversation Model
class Conversation(Base):
    __tablename__ = "conversations"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    client_id = Column(String(36), ForeignKey("clients.id"), nullable=True)
    lead_id = Column(String(36), ForeignKey("leads.id"), nullable=True)
    channel = Column(String(50), nullable=False) # whatsapp, email, chat, google_chat
    status = Column(String(50), default="active", nullable=False)
    summary = Column(Text, nullable=True)
    sentiment = Column(String(50), default="neutral")
    transcript = Column(JSON, default=[]) # List of message objects
    last_message_at = Column(DateTime, nullable=False, default=datetime.datetime.utcnow)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    client = relationship("Client", back_populates="conversations")
    lead = relationship("Lead", back_populates="conversations")

# 13. AgentAction Model
class AgentAction(Base):
    __tablename__ = "agent_actions"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    agent_name = Column(String(100), nullable=False)
    action_type = Column(String(100), nullable=False)
    status = Column(String(50), nullable=False) # started, completed, failed
    description = Column(Text, nullable=True)
    input_payload = Column(JSON, default={})
    output_payload = Column(JSON, default={})
    duration_ms = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

# 14. Escalation Model
class Escalation(Base):
    __tablename__ = "escalations"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    task_id = Column(String(36), ForeignKey("tasks.id"), nullable=True)
    agent_name = Column(String(100), nullable=False)
    title = Column(String(255), nullable=False)
    reason = Column(Text, nullable=False)
    priority = Column(String(50), default="high", nullable=False)
    status = Column(String(50), default="raised", nullable=False) # raised, resolved, etc.
    assigned_user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    related_entity_type = Column(String(50), nullable=False)
    related_entity_id = Column(String(36), nullable=False)
    resolved_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    assigned_user = relationship("User", back_populates="escalations")
    task = relationship("Task")

# 15. HumanApproval Model
class HumanApproval(Base):
    __tablename__ = "human_approvals"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    requested_by = Column(String(100), nullable=False)
    action_name = Column(String(100), nullable=False)
    description = Column(Text, nullable=False)
    payload = Column(JSON, nullable=False)
    status = Column(String(50), default="pending", nullable=False) # pending, approved, rejected
    reviewed_by = Column(String(36), ForeignKey("users.id"), nullable=True)
    review_notes = Column(Text, nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    reviewed_by_user = relationship("User", back_populates="approvals_reviewed")

# 16. Candidate Model
class Candidate(Base):
    __tablename__ = "candidates"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    lead_id = Column(String(36), ForeignKey("leads.id"), unique=True, nullable=False)
    onboarding_status = Column(String(50), default="not_started", nullable=False) # not_started, completed, etc.
    training_progress_pct = Column(Numeric(5, 2), default=0.00)
    has_credentials = Column(Boolean, default=False, nullable=False)
    metadata_json = Column("metadata", JSON, default={})
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    lead = relationship("Lead", back_populates="candidate")

# 17. StrategyProposal Model
class StrategyProposal(Base):
    __tablename__ = "strategy_proposals"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    status = Column(String(50), default="draft", nullable=False) # draft, approved, archived
    created_by = Column(String(100), default="plauto_mind", nullable=False)
    approved_by = Column(String(36), ForeignKey("users.id"), nullable=True)
    metadata_json = Column("metadata", JSON, default={})
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    approved_by_user = relationship("User", back_populates="strategy_proposals")


# 18. Source Document Model
class SourceDocument(Base):
    __tablename__ = "source_documents"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    storage_provider = Column(String(50), default="local_file", nullable=False)
    google_drive_file_id = Column(String(255), unique=True, nullable=True)
    google_drive_parent_id = Column(String(255), nullable=True)
    shared_drive_id = Column(String(255), nullable=True)
    source_uri = Column(String(1000), unique=True, nullable=False)
    web_view_link = Column(String(1000), nullable=True)
    original_filename = Column(String(255), nullable=False)
    mime_type = Column(String(100), nullable=True)
    source_category = Column(String(100), nullable=False)
    insurer_id = Column(String(50), nullable=True)
    product_branch = Column(String(50), nullable=True)
    source_period_start = Column(Date, nullable=True)
    source_period_end = Column(Date, nullable=True)
    drive_created_at = Column(DateTime, nullable=True)
    drive_modified_at = Column(DateTime, nullable=True)
    detected_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    archived_at = Column(DateTime, nullable=True)
    metadata_json = Column("metadata", JSON, default={})

    ingestion_runs = relationship("IngestionRun", back_populates="source_document")
    ingestion_records = relationship("IngestionRecord", back_populates="source_document")


# 19. Ingestion Run Model
class IngestionRun(Base):
    __tablename__ = "ingestion_runs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    source_document_id = Column(String(36), ForeignKey("source_documents.id"), nullable=False)
    parser_name = Column(String(100), nullable=False)
    parser_version = Column(String(50), nullable=False)
    status = Column(String(50), default="started", nullable=False)
    started_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    rows_read = Column(Integer, default=0, nullable=False)
    rows_imported = Column(Integer, default=0, nullable=False)
    rows_updated = Column(Integer, default=0, nullable=False)
    rows_skipped = Column(Integer, default=0, nullable=False)
    rows_failed = Column(Integer, default=0, nullable=False)
    error_summary = Column(Text, nullable=True)
    metadata_json = Column("metadata", JSON, default={})

    source_document = relationship("SourceDocument", back_populates="ingestion_runs")
    records = relationship("IngestionRecord", back_populates="ingestion_run")
    data_quality_issues = relationship("DataQualityIssue", back_populates="ingestion_run")


# 20. Ingestion Record Model
class IngestionRecord(Base):
    __tablename__ = "ingestion_records"
    __table_args__ = (
        UniqueConstraint("source_document_id", "sheet_name", "row_number", "row_hash", name="uq_ingestion_record_row_identity"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    ingestion_run_id = Column(String(36), ForeignKey("ingestion_runs.id"), nullable=False)
    source_document_id = Column(String(36), ForeignKey("source_documents.id"), nullable=False)
    sheet_name = Column(String(100), nullable=True)
    row_number = Column(Integer, nullable=True)
    row_hash = Column(String(64), nullable=False)
    source_payload = Column(JSON, nullable=False)
    normalized_payload = Column(JSON, default={})
    related_object_type = Column(String(50), nullable=True)
    related_object_id = Column(String(36), nullable=True)
    reconciliation_status = Column(String(50), nullable=False)
    reconciliation_confidence = Column(Numeric(5, 2), nullable=True)
    issue_summary = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    ingestion_run = relationship("IngestionRun", back_populates="records")
    source_document = relationship("SourceDocument", back_populates="ingestion_records")
    payment_evidence_records = relationship("PaymentEvidenceRecord", back_populates="ingestion_record")
    reconciliation_matches = relationship("ReconciliationMatch", back_populates="ingestion_record")
    data_quality_issues = relationship("DataQualityIssue", back_populates="ingestion_record")


# 21. Payment Evidence Record Model
class PaymentEvidenceRecord(Base):
    __tablename__ = "payment_evidence_records"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    ingestion_record_id = Column(String(36), ForeignKey("ingestion_records.id"), nullable=False)
    payment_id = Column(String(36), ForeignKey("payments.id"), nullable=True)
    policy_id = Column(String(36), ForeignKey("policies.id"), nullable=True)
    client_id = Column(String(36), ForeignKey("clients.id"), nullable=True)
    insurer_id = Column(String(50), nullable=True)
    product_branch = Column(String(50), nullable=True)
    policy_number = Column(String(100), nullable=True)
    client_name = Column(String(255), nullable=True)
    evidence_type = Column(String(50), nullable=False)
    evidence_date = Column(Date, nullable=True)
    expected_amount = Column(Numeric(14, 2), nullable=True)
    paid_amount = Column(Numeric(14, 2), nullable=True)
    gross_commission_amount = Column(Numeric(14, 2), nullable=True)
    net_commission_amount = Column(Numeric(14, 2), nullable=True)
    tax_amount = Column(Numeric(14, 2), nullable=True)
    receipt_number = Column(String(100), nullable=True)
    insurer_reference = Column(String(255), nullable=True)
    receipt_status = Column(String(100), nullable=True)
    policy_status_source = Column(String(100), nullable=True)
    collection_channel = Column(String(255), nullable=True)
    commission_type = Column(String(255), nullable=True)
    payment_application_status = Column(String(100), nullable=True)
    reconciliation_status = Column(String(50), nullable=False)
    reconciliation_confidence = Column(Numeric(5, 2), nullable=True)
    metadata_json = Column("metadata", JSON, default={})
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    ingestion_record = relationship("IngestionRecord", back_populates="payment_evidence_records")
    payment = relationship("Payment", foreign_keys=[payment_id])
    policy = relationship("Policy", foreign_keys=[policy_id])
    client = relationship("Client", foreign_keys=[client_id])


# 22. Reconciliation Match Model
class ReconciliationMatch(Base):
    __tablename__ = "reconciliation_matches"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    ingestion_record_id = Column(String(36), ForeignKey("ingestion_records.id"), nullable=False)
    matched_object_type = Column(String(50), nullable=False)
    matched_object_id = Column(String(36), nullable=True)
    match_basis = Column(String(100), nullable=False)
    confidence = Column(Numeric(5, 2), nullable=False)
    status = Column(String(50), nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    ingestion_record = relationship("IngestionRecord", back_populates="reconciliation_matches")


# 23. Data Quality Issue Model
class DataQualityIssue(Base):
    __tablename__ = "data_quality_issues"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    ingestion_run_id = Column(String(36), ForeignKey("ingestion_runs.id"), nullable=True)
    ingestion_record_id = Column(String(36), ForeignKey("ingestion_records.id"), nullable=True)
    related_object_type = Column(String(50), nullable=True)
    related_object_id = Column(String(36), nullable=True)
    severity = Column(String(50), nullable=False)
    issue_type = Column(String(100), nullable=False)
    issue_summary = Column(Text, nullable=False)
    status = Column(String(50), default="open", nullable=False)
    assigned_user_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    ingestion_run = relationship("IngestionRun", back_populates="data_quality_issues")
    ingestion_record = relationship("IngestionRecord", back_populates="data_quality_issues")
    assigned_user = relationship("User", foreign_keys=[assigned_user_id])


# Helper block to create local SQLite database for development
def create_all_tables():
    """Initializes the database schema."""
    Base.metadata.create_all(bind=engine)

if __name__ == "__main__":
    print("Initializing local development database tables...")
    create_all_tables()
    print("Database tables initialized successfully!")
