from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship, Session
from datetime import datetime, timezone
from typing import List
import os
from base64 import b64decode

# FastAPIインスタンス作成
app = FastAPI()

# CORSの設定 フロントエンドからの接続を許可する部分
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://tech0-gen8-step4-pos-app-112.azurewebsites.net"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# Base64エンコードされた証明書を取得
cert_base64 = os.getenv('SSL_CERTIFICATE')

# Base64デコードして証明書をバイナリデータに変換
cert_data = b64decode(cert_base64)

# 証明書ファイルを作成する
with open('/tmp/DigiCertGlobalRootCA.crt.pem', 'wb') as cert_file:
    cert_file.write(cert_data)


# データベース設定
DATABASE_URL = f"mysql+mysqlconnector://{os.getenv('MYSQL_USER')}:{os.getenv('MYSQL_PASSWORD')}@{os.getenv('MYSQL_HOST')}/{os.getenv('MYSQL_DB')}"ssl_ca=/tmp/DigiCertGlobalRootCA.crt.pem&ssl_verify_cert=true"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# 商品マスターテーブル
class Product(Base):
    __tablename__ = "m_product_asami"
    prd_id = Column(Integer, primary_key=True, index=True)
    code = Column(String(13), unique=True, index=True)
    name = Column(String(50))
    price = Column(Integer)

    # 商品に関連する取引明細を定義
    transaction_details = relationship("TransactionDetail", back_populates="product")

# 取引テーブル
class Transaction(Base):
    __tablename__ = "transactions_asami"
    trd_id = Column(Integer, primary_key=True, index=True)
    current_time = datetime.now(timezone.utc)
    total_amt = Column(Integer)
    emp_cd = Column(String(10))
    store_cd = Column(String(10))
    pos_no = Column(String(10))
    

    # 取引に関連する取引明細を定義
    transaction_details = relationship("TransactionDetail", back_populates="transaction")

# 取引明細テーブル
class TransactionDetail(Base):
    __tablename__ = "transaction_details_asami"
    DTL_ID = Column(Integer, primary_key=True, autoincrement=True)  # autoincrement=True を追加
    trd_id = Column(Integer, ForeignKey('transactions_asami.trd_id'), primary_key=True)
    prd_id = Column(Integer, ForeignKey('m_product_asami.prd_id'))
    prd_code = Column(String(13))
    prd_name = Column(String(50))
    prd_price = Column(Integer)

    # 取引明細と関連する取引および商品を定義
    transaction = relationship("Transaction", back_populates="transaction_details")
    product = relationship("Product", back_populates="transaction_details")

# データベースに接続
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# 商品情報検索用のリクエストボディ
class ProductRequest(BaseModel):
    code: str

# 購入リストのリクエストボディ
class PurchaseRequest(BaseModel):
    emp_cd: str
    store_cd: str
    pos_no: str
    items: List[dict]  # 商品リストを辞書形式で


# 商品検索API
@app.post("/search_product")
def search_product(request: ProductRequest, db: Session = Depends(get_db)): 
    product = db.query(Product).filter(Product.code == request.code).first()
    
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return {"name": product.name, "price": product.price}

# 購入処理API
@app.post("/purchase")
def purchase(request: PurchaseRequest, db: Session = Depends(get_db)):  
    # 取引を作成
    transaction = Transaction(emp_cd=request.emp_cd, store_cd=request.store_cd, pos_no=request.pos_no, total_amt=0)
    db.add(transaction)
    db.commit()
    db.refresh(transaction)

    total_amt = 0
    purchased_items = []  # 購入した商品を格納するリスト

    # 取引明細を作成
    for item in request.items:
        product = db.query(Product).filter(Product.code == item['product_code']).first()
        if not product:
            raise HTTPException(status_code=404, detail=f"Product {item['product_code']} not found")

        # 取引明細を追加
        transaction_detail = TransactionDetail(
            trd_id=transaction.trd_id,
            prd_id=product.prd_id,
            prd_code=product.code,
            prd_name=product.name,
            prd_price=product.price
        )
        db.add(transaction_detail)
        total_amt += product.price * item['quantity']
        purchased_items.append({
            "name": product.name,
            "price": product.price,
            "quantity": item['quantity'],
            "total": product.price * item['quantity']
        })

    # 合計金額を更新
    transaction.total_amt = total_amt
    db.commit()

    return {"message": "Purchase completed", "total_amount": total_amt, "purchased_items": purchased_items}

# データベースのテーブル作成
Base.metadata.create_all(bind=engine)
