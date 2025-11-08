# Website Changes Checklist - PayGate Prime

## Overview
This document outlines the implementation plan for critical website changes to www.paygateprime.com. All changes are focused on improving UX and adding proper validation.

---

## 1. Remove Analytics Button from Dashboard

### Current State
- **Location**: `GCRegisterWeb-10-26/src/pages/DashboardPage.tsx:156`
- **Issue**: Analytics button exists but has no functionality

### Implementation Steps
- [ ] Navigate to `DashboardPage.tsx`
- [ ] Locate the button group section (lines 148-157)
- [ ] Remove the Analytics button entirely
- [ ] Adjust button group layout if needed

### Code Reference
```tsx
// Current (lines 148-157)
<div className="btn-group">
  <button className="btn btn-secondary" style={{ flex: 1 }} onClick={() => navigate(`/edit/${channel.open_channel_id}`)}>
    Edit
  </button>
  <button className="btn btn-secondary">Analytics</button>  // REMOVE THIS
</div>
```

---

## 2. Add DELETE Button to Dashboard

### Current State
- **Backend API**: Already implemented in `channelService.ts:25-28`
- **Frontend**: No DELETE button currently exists

### Implementation Steps
- [ ] Add DELETE button to replace Analytics button in `DashboardPage.tsx`
- [ ] Style button with red color scheme to indicate destructive action
- [ ] Implement click handler with confirmation dialog
- [ ] Add state management for delete operation (loading, error handling)
- [ ] Use `channelService.deleteChannel(channelId)` API call
- [ ] Show success/error feedback to user
- [ ] Refresh channel list after successful deletion
- [ ] Handle edge cases (last channel, active subscriptions, etc.)

### Code Structure
```tsx
// Pseudo-code structure
const handleDeleteChannel = async (channelId: string, channelTitle: string) => {
  // 1. Show confirmation dialog
  const confirmed = window.confirm(`Are you sure you want to delete "${channelTitle}"? This action cannot be undone.`);

  // 2. If confirmed, call API
  if (confirmed) {
    try {
      await channelService.deleteChannel(channelId);
      // 3. Refetch channels or update state
      queryClient.invalidateQueries(['channels']);
      // 4. Show success message
    } catch (error) {
      // 5. Handle error
      setError(error.message);
    }
  }
};
```

### Design Specifications
- **Button Color**: Red (`#DC2626` or similar)
- **Text**: "Delete" or "🗑️ Delete"
- **Position**: Replace Analytics button position
- **Style**: Should clearly indicate destructive action
- **Hover State**: Darker red on hover

---

## 3. Fix Default Values for Payout Network & Currency

### Current State
- **Location**: `RegisterChannelPage.tsx:44-68` (useEffect hook)
- **Issue**: Defaults to first available network/currency (e.g., AVAXC & USDC)
- **Expected**: Should default to placeholder values

### Implementation Steps
- [ ] Navigate to `RegisterChannelPage.tsx`
- [ ] Locate the `loadMappings` function in useEffect (lines 44-68)
- [ ] Remove automatic default setting logic (lines 50-58)
- [ ] Set initial state to empty strings (already done in state initialization lines 38-39)
- [ ] Verify dropdowns show "-- Select Network --" and "-- Select Currency --" as defaults

### Current Code to Modify
```tsx
// REMOVE THESE LINES (50-58)
// Set default values
const networks = Object.keys(response.data.networks_with_names);
if (networks.length > 0) {
  setClientPayoutNetwork(networks[0]);
  const currencies = response.data.network_to_currencies[networks[0]];
  if (currencies && currencies.length > 0) {
    setClientPayoutCurrency(currencies[0].currency);
  }
}
```

### Expected Result
- Network dropdown defaults to: `-- Select Network --`
- Currency dropdown defaults to: `-- Select Currency --`
- Both fields remain required (validation error if not selected)

---

## 4. Add Payout Strategy Minimum Validation (20.00 USD)

### Current State
- **Locations**:
  - `RegisterChannelPage.tsx:585-599` (Threshold input)
  - `EditChannelPage.tsx:627-641` (Threshold input)
- **Issue**: Only checks if value > 0, no minimum floor of $20.00

### Implementation Steps
- [ ] Add client-side validation in `RegisterChannelPage.tsx`
  - [ ] Update the input onChange handler to validate minimum
  - [ ] Add validation check in handleSubmit function
  - [ ] Add visual feedback (error message/border) for invalid values
- [ ] Repeat same steps for `EditChannelPage.tsx`
- [ ] Ensure validation message is clear: "Minimum threshold is $20.00"

### Validation Logic
```tsx
// Add to input field
<input
  type="number"
  step="0.01"
  min="20.00"  // Add HTML5 validation
  placeholder="100.00"
  value={payoutThresholdUsd}
  onChange={(e) => {
    const value = e.target.value;
    setPayoutThresholdUsd(value);
    // Optional: Show inline validation error
    if (parseFloat(value) < 20.00 && value !== '') {
      setThresholdError('Minimum threshold is $20.00');
    } else {
      setThresholdError(null);
    }
  }}
  required
/>

// Add to handleSubmit validation
if (payoutStrategy === 'threshold' && parseFloat(payoutThresholdUsd) < 20.00) {
  throw new Error('Threshold amount must be at least $20.00');
}
```

### Regex Pattern (if using pattern attribute)
```
pattern="^([2-9]\d|[1-9]\d{2,})(\.\d{1,2})?$"
```
This matches: 20.00 or higher

### Files to Update
1. `GCRegisterWeb-10-26/src/pages/RegisterChannelPage.tsx`
2. `GCRegisterWeb-10-26/src/pages/EditChannelPage.tsx`

---

## 5. Add Tier Price Minimum Validation (4.99 USD)

### Current State
- **Locations**:
  - `RegisterChannelPage.tsx`:
    - Tier 1 (Gold): lines 385-407
    - Tier 2 (Silver): lines 410-440
    - Tier 3 (Bronze): lines 442-472
  - `EditChannelPage.tsx`:
    - Tier 1 (Gold): lines 422-450
    - Tier 2 (Silver): lines 452-482
    - Tier 3 (Bronze): lines 484-514
- **Issue**: No minimum price validation

### Implementation Steps
- [ ] Add HTML5 min attribute to all tier price inputs
- [ ] Add client-side validation in handleSubmit for all active tiers
- [ ] Add onChange validation with visual feedback (optional)
- [ ] Update validation error messages to specify $4.99 minimum
- [ ] Apply to both RegisterChannelPage and EditChannelPage

### Validation Logic for Each Tier
```tsx
// Tier 1 (Always Required)
<input
  type="number"
  step="0.01"
  min="4.99"  // Add HTML5 validation
  placeholder="50.00"
  value={sub1Price}
  onChange={(e) => setSub1Price(e.target.value)}
  required
/>

// Add to handleSubmit
if (parseFloat(sub1Price) < 4.99) {
  throw new Error('Tier 1 price must be at least $4.99');
}

// Repeat for Tier 2 (if tierCount >= 2)
if (tierCount >= 2 && parseFloat(sub2Price) < 4.99) {
  throw new Error('Tier 2 price must be at least $4.99');
}

// Repeat for Tier 3 (if tierCount === 3)
if (tierCount === 3 && parseFloat(sub3Price) < 4.99) {
  throw new Error('Tier 3 price must be at least $4.99');
}
```

### Regex Pattern (if using pattern attribute)
```
pattern="^([4-9](\.\d{1,2})?|[1-9]\d+(\.\d{1,2})?)$"
```
This matches: 4.99 or higher

### Files to Update
1. `GCRegisterWeb-10-26/src/pages/RegisterChannelPage.tsx`
   - Line 388: Tier 1 Price input
   - Line 419: Tier 2 Price input (conditional)
   - Line 450: Tier 3 Price input (conditional)
   - Lines 119-143: handleSubmit validation section

2. `GCRegisterWeb-10-26/src/pages/EditChannelPage.tsx`
   - Line 430: Tier 1 Price input
   - Line 461: Tier 2 Price input (conditional)
   - Line 493: Tier 3 Price input (conditional)
   - Lines 152-176: handleSubmit validation section

---

## Testing Checklist

### After Implementation, Verify:

#### 1. Analytics Button Removal
- [ ] Dashboard loads without Analytics button
- [ ] Button group layout looks correct with only Edit button
- [ ] No console errors

#### 2. DELETE Button Functionality
- [ ] DELETE button appears in red
- [ ] Clicking DELETE shows confirmation dialog
- [ ] Canceling confirmation does nothing
- [ ] Confirming deletion removes channel from dashboard
- [ ] Success/error messages display correctly
- [ ] Channel list refreshes after deletion
- [ ] Test with single channel (edge case)
- [ ] Test with multiple channels

#### 3. Default Network/Currency Values
- [ ] New channel registration shows "-- Select Network --" by default
- [ ] New channel registration shows "-- Select Currency --" by default
- [ ] Form validation prevents submission without selections
- [ ] Error message is clear when fields not selected

#### 4. Payout Strategy Validation
- [ ] Cannot submit with threshold < $20.00
- [ ] Error message displays: "Threshold amount must be at least $20.00"
- [ ] HTML5 validation prevents values below 20.00 (if min attribute works)
- [ ] Valid values ($20.00, $50.00, $100.00) work correctly
- [ ] Test in both Register and Edit pages

#### 5. Tier Price Validation
- [ ] Cannot submit Tier 1 with price < $4.99
- [ ] Cannot submit Tier 2 with price < $4.99 (when active)
- [ ] Cannot submit Tier 3 with price < $4.99 (when active)
- [ ] Error messages specify which tier has invalid price
- [ ] Valid values ($4.99, $5.00, $50.00) work correctly
- [ ] Test in both Register and Edit pages
- [ ] Test with 1, 2, and 3 tiers active

---

## Deployment Steps

1. **Build Frontend**
   ```bash
   cd GCRegisterWeb-10-26
   npm run build
   ```

2. **Test Build Locally**
   - Verify all changes in production build
   - Test all validation scenarios

3. **Deploy to GCS Bucket**
   ```bash
   gsutil -m rsync -r -d dist gs://[BUCKET_NAME]
   ```

4. **Verify Live Site**
   - Test all functionality on www.paygateprime.com
   - Check browser console for errors
   - Test on mobile devices

---

## Implementation Priority

### Phase 1 (High Priority - UI/UX)
1. Remove Analytics button
2. Add DELETE button with full functionality
3. Fix default network/currency values

### Phase 2 (Medium Priority - Validation)
4. Add payout strategy minimum validation ($20.00)
5. Add tier price minimum validation ($4.99)

---

## Notes

- All changes are client-side only (no backend modifications required)
- DELETE API endpoint already exists: `channelService.deleteChannel()`
- Validation is primarily client-side for better UX
- Backend should also validate these minimums for security
- Consider adding inline validation feedback for better UX
- All regex patterns provided are for client-side validation only

---

## File Summary

**Files to Modify:**
1. `GCRegisterWeb-10-26/src/pages/DashboardPage.tsx`
2. `GCRegisterWeb-10-26/src/pages/RegisterChannelPage.tsx`
3. `GCRegisterWeb-10-26/src/pages/EditChannelPage.tsx`

**Files Already Complete:**
- `GCRegisterWeb-10-26/src/services/channelService.ts` (DELETE API exists)

**Total Estimated Implementation Time:** 2-3 hours

---

## Success Criteria

✅ Analytics button removed from dashboard
✅ Red DELETE button functional with confirmation
✅ Network/Currency default to placeholder values
✅ Payout threshold enforces $20.00 minimum
✅ All tier prices enforce $4.99 minimum
✅ All validations show clear error messages
✅ Website builds and deploys successfully
✅ All functionality tested and working on live site
