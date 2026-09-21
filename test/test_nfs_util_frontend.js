const assert = require('assert');
const fs = require('fs');
const vm = require('vm');

const scriptPath = '/www/server/jh-panel/plugins/nfs-util/js/nfs-util.js';

const state = {
  rows: [
    { value: '1', checked: false },
    { value: '2', checked: false },
  ],
  selectAll: { checked: false, indeterminate: false },
  batchVisible: false,
  safeMessage: null,
};

function selection(items) {
  return {
    length: items.length,
    toArray: () => items,
    prop(name, value) {
      if (typeof value === 'undefined') {
        return items[0] && items[0][name];
      }
      items.forEach((item) => { item[name] = value; });
      return this;
    },
    toggle(value) {
      state.batchVisible = Boolean(value);
      return this;
    },
    find(selector) {
      return query(selector);
    },
  };
}

function query(selector) {
  if (selector === '.nfs-util-panel') {
    return selection([{}]);
  }
  if (selector.includes('input.nfs-row-check:checked')) {
    return selection(state.rows.filter((item) => item.checked));
  }
  if (selector.includes('input.nfs-row-check')) {
    return selection(state.rows);
  }
  if (selector.includes('input.nfs-check-all')) {
    return selection([state.selectAll]);
  }
  if (selector.includes('button[data-nfs-batch]')) {
    return selection([{}]);
  }
  return selection([]);
}

function $(selector) {
  return query(selector);
}

$.parseJSON = JSON.parse;

const context = {
  console,
  $, 
  encodeURIComponent,
  setTimeout: (callback) => callback(),
  layer: { msg() {}, confirm() {}, close() {}, open() {} },
  safeMessage(title, message, callback) {
    state.safeMessage = { title, message, callback };
  },
  document: {},
};
vm.createContext(context);
vm.runInContext(fs.readFileSync(scriptPath, 'utf8'), context, { filename: scriptPath });

context.syncSelectionState();
assert.deepStrictEqual(Array.from(context.checkedIds), []);
assert.strictEqual(state.batchVisible, false);
assert.strictEqual(state.selectAll.checked, false);

state.rows[0].checked = true;
context.checkSelect();
assert.deepStrictEqual(Array.from(context.checkedIds), ['1']);
assert.strictEqual(state.batchVisible, true);
assert.strictEqual(state.selectAll.checked, false);
assert.strictEqual(state.selectAll.indeterminate, true);

context.checkSelectAll({ checked: true });
assert.deepStrictEqual(Array.from(context.checkedIds), ['1', '2']);
assert.strictEqual(state.selectAll.checked, true);
assert.strictEqual(state.selectAll.indeterminate, false);

context.checkSelectAll({ checked: false });
assert.deepStrictEqual(Array.from(context.checkedIds), []);
assert.strictEqual(state.batchVisible, false);

state.rows[0].checked = true;
context.syncSelectionState();
let unmountExecuted = false;
context.runMountBatch = () => { unmountExecuted = true; };
context.unmountBatch();
assert.strictEqual(unmountExecuted, false);
state.rows[0].checked = false;
context.syncSelectionState();

context.checkedIds = ['1', 'missing'];
const validIds = ['1', '2'];
context.checkedIds = context.checkedIds.filter((id) => validIds.includes(String(id)));
assert.deepStrictEqual(Array.from(context.checkedIds), ['1']);

const rawResponse = context.parsePluginResponse({ status: true, data: 'echo ok' });
assert.strictEqual(rawResponse.status, true);
assert.strictEqual(rawResponse.data, 'echo ok');

const structuredResponse = context.parsePluginResponse({
  status: true,
  data: JSON.stringify({ status: false, msg: 'invalid action' }),
});
assert.strictEqual(structuredResponse.status, false);
assert.strictEqual(structuredResponse.msg, 'invalid action');

const source = fs.readFileSync(scriptPath, 'utf8');
assert.strictEqual(source.includes('批量删除'), true);

state.rows[0].checked = true;
state.rows[1].checked = true;
context.syncSelectionState();
context.tableData = [
  { id: '1', name: '<危险名称>' },
  { id: '2', name: '普通挂载' },
];
let deleteRequests = 0;
let refreshCount = 0;
context.requestApi = (method, args, callback) => {
  deleteRequests += 1;
  assert.strictEqual(method, 'mount_batch_delete');
  assert.strictEqual(args.ids, '1,2');
  callback({
    status: true,
    data: JSON.stringify({
      status: true,
      msg: '处理完成：删除2项，跳过0项',
      data: { deleted: ['1', '2'], missing: [] },
    }),
  });
};
context.refreshTable = () => { refreshCount += 1; };
context.deleteBatch();
assert.strictEqual(deleteRequests, 0);
assert.strictEqual(state.safeMessage.title, '确认批量删除挂载记录');
assert.strictEqual(state.safeMessage.message.includes('&lt;危险名称&gt;'), true);
assert.strictEqual(state.safeMessage.message.includes('不会卸载现有挂载'), true);
assert.strictEqual(state.safeMessage.message.includes('不会清理自动挂载配置'), true);

state.safeMessage.callback();
assert.strictEqual(deleteRequests, 1);
assert.strictEqual(refreshCount, 1);
assert.deepStrictEqual(Array.from(context.checkedIds), []);
console.log('ok');
