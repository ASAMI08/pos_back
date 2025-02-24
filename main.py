from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import List
from connect import get_db, Product, Transaction, TransactionDetail  # connect.py から必要なものをインポート

# FastAPIインスタンス作成
app = FastAPI()

# CORSの設定 フロントエンドからの接続を許可する部分
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://tech0-gen8-step4-pos-app-111.azurewebsites.net",
                   "http://localhost:3000",
                   "http://127.0.0.1:8000" 
], 
    
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

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
