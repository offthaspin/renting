@mpesa_bp.route('/payment_callback/validate', methods=['POST'])
@csrf_exempt  # ✅ Required for Daraja callbacks
def mpesa_validate():
    """Daraja calls this to validate before completing the payment.
    Expect JSON with BillRefNumber / AccountReference and an OwnerID (multi-user).
    """
    data = request.get_json(silent=True) or {}
    logger.info("VALIDATION payload: %s", data)

    bill_ref = (data.get('BillRefNumber') or data.get('AccountReference') or data.get('BillRef') or "").strip()
    owner_id = data.get('OwnerID') or data.get('owner_id') or data.get('UserID')

    # Try resolving owner_id via shortcode/business code if missing
    if not owner_id:
        shortcode = (data.get('ShortCode') or data.get('BusinessShortCode') or data.get('Shortcode') or "").strip()
        if shortcode and _USE_ORM and LandlordSettings is not None:
            try:
                ls = LandlordSettings.query.filter(
                    (LandlordSettings.paybill_number == shortcode) |
                    (LandlordSettings.till_number == shortcode) |
                    (LandlordSettings.send_money_number == shortcode)
                ).first()
                if ls:
                    owner_id = ls.user_id
            except Exception:
                logger.exception("ORM lookup by shortcode failed")

    if not owner_id:
        logger.warning("Validation failed: missing OwnerID")
        return jsonify({"ResultCode": 1, "ResultDesc": "Missing OwnerID"}), 200

    # Fetch owner
    owner = None
    if _USE_ORM and User is not None:
        owner = User.query.filter_by(id=owner_id).first()
        if not owner:
            logger.warning("Validation failed: Owner %s not found", owner_id)
            return jsonify({"ResultCode": 1, "ResultDesc": "Invalid Owner"}), 200

    # Try finding tenant by house_no first, then phone fragment
    tenant = None
    if _USE_ORM and Tenant is not None:
        if bill_ref:
            tenant = Tenant.query.filter_by(owner_id=owner.id, house_no=bill_ref).first()
        if not tenant and bill_ref.isdigit():
            tenant = Tenant.query.filter(Tenant.owner_id == owner.id, Tenant.phone.like(f"%{bill_ref}%")).first()

    if tenant:
        logger.info("Validation passed for owner %s tenant %s", owner_id, tenant.name)
        return jsonify({"ResultCode": 0, "ResultDesc": "Validation Passed"}), 200
    else:
        logger.warning("Validation failed for bill_ref=%s under Owner=%s", bill_ref, owner_id)
        return jsonify({"ResultCode": 1, "ResultDesc": "Invalid tenant reference"}), 200


# make sure this import exists at the top

@mpesa_bp.route('/payment_callback/confirmation', methods=['POST'])
@csrf_exempt
def mpesa_confirmation():
    """Daraja will POST payment confirmation here. ORM-safe, owner optional."""
    payload = request.get_json(silent=True) or {}
    logger.info("CONFIRMATION payload: %s", payload)

    body = payload.get('Body') if 'Body' in payload else payload
    stk_callback = body.get('stkCallback') if 'stkCallback' in body else None

    try:
        # Parse payment details
        if stk_callback:
            checkout_request_id = stk_callback.get('CheckoutRequestID')
            items = stk_callback.get('CallbackMetadata', {}).get('Item', [])
            data_map = {it.get('Name'): it.get('Value') for it in items if isinstance(it, dict)}
            tx_id = data_map.get('MpesaReceiptNumber') or checkout_request_id
            amount_val = float(data_map.get('Amount', 0))
            phone = data_map.get('PhoneNumber')
            account_ref = data_map.get('AccountReference') or DEFAULT_PAYBILL
        else:
            tx_id = body.get('TransID') or body.get('TransactionID') or body.get('MpesaReceiptNumber')
            amount_val = float(body.get('Amount', 0))
            phone = body.get('MSISDN') or body.get('Msisdn')
            account_ref = body.get('BillRefNumber') or DEFAULT_PAYBILL

        if not tx_id or not amount_val:
            return jsonify({"ResultCode": 1, "ResultDesc": "Missing data"}), 200

        msisdn_norm = _normalize_msisdn(phone)

        # Owner resolution
        owner_id = body.get('OwnerID') or request.headers.get('X-Owner-ID')
        owner = None

        if not owner_id:
            business_code = account_ref.split("#")[0].strip() if "#" in account_ref else account_ref

            if LandlordSettings is not None:
                ls = LandlordSettings.query.filter(
                    (LandlordSettings.paybill_number == business_code) |
                    (LandlordSettings.till_number == business_code) |
                    (LandlordSettings.send_money_number == business_code)
                ).first()
                if ls:
                    owner_id = ls.user_id

            if not owner_id and User is not None:
                u = User.query.filter(
                    (User.paybill_number == business_code) |
                    (User.till_number == business_code) |
                    (User.phone_number == business_code)
                ).first()
                if u:
                    owner_id = u.id

        if owner_id and User is not None:
            owner = User.query.get(owner_id)

        # Optional Daraja verification
        try:
            verify_transaction_with_daraja(str(tx_id), amount_val, msisdn_norm or "", account_ref)
        except Exception:
            logger.exception("Daraja verification failed, continuing anyway")

        # Process payment safely
        try:
            result = process_payment_orm(
                account_ref,
                amount_val,
                str(tx_id),
                note="Daraja confirmation",
                msisdn=msisdn_norm
            )
        except Exception:
            logger.exception("Failed in process_payment_orm")
            result = {"ok": False}

        if result.get('ok'):
            logger.info("Payment recorded: %s", tx_id)
            return jsonify({"ResultCode": 0, "ResultDesc": "Confirmation received successfully"}), 200
        else:
            # Fallback logging for simulation
            logger.warning(
                "[SIMULATION] Payment not saved in ORM → Account: %s | Amount: %s | TxID: %s | Phone: %s",
                account_ref, amount_val, tx_id, msisdn_norm
            )
            return jsonify({"ResultCode": 0, "ResultDesc": "Confirmation received (simulated)"}), 200

    except Exception:
        logger.exception("Error handling confirmation")
        return jsonify({"ResultCode": 1, "ResultDesc": "Processing error"}), 200



<div class="alert alert-primary small" role="alert">
        <strong>Security:</strong> Keep consumer secrets & passkeys private. They are stored in the DB — do not commit them.
    </div>