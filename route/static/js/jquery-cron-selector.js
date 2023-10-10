

/**
 * 用法：
 * 
 * HTML：
 * <div id="testCronSelector"></div>
 * 
 * 初始化：$("#testCronSelector").createCronSelector(value);
 * 获取当前配置：$("#testCronSelector").getCronData();
 */

var cycleArray = { 'day': '每天', 'day-n': 'N天', 'hour': '每小时', 'hour-n': 'N小时', 'minute-n': 'N分钟', 'week': '每星期', 'month': '每月' }
var weekArray = { 1: '周一', 2: '周二', 3: '周三', 4: '周四', 5: '周五', 6: '周六', 0: '周日' }

;(function () {
  $.fn.extend({
    reportCycleValue: {},
    createCronSelector: function (value = {}) {
      this.reportCycleValue = value;
      var html = "<div class='report-cycle-main pd20 pb70'>\
        <div class='clearfix plan'>\
          <div class='dropdown plancycle pull-left mr20'>\
            <button class='btn btn-default dropdown-toggle' type='button' id='cycle' data-toggle='dropdown' style='width:94px'>\
                              <b val='" + (value.type || 'week') + "'>" + cycleArray[value.type || 'week'] + "</b>\
                              <span class='caret'></span>\
                          </button>\
            <ul class='dropdown-menu' role='menu' aria-labelledby='cycle'>\
              <li><a role='menuitem' tabindex='-1' href='javascript:;' value='day'>每天</a></li>\
              <li><a role='menuitem' tabindex='-1' href='javascript:;' value='day-n'>N天</a></li>\
              <li><a role='menuitem' tabindex='-1' href='javascript:;' value='hour'>每小时</a></li>\
              <li><a role='menuitem' tabindex='-1' href='javascript:;' value='hour-n'>N小时</a></li>\
              <li><a role='menuitem' tabindex='-1' href='javascript:;' value='minute-n'>N分钟</a></li>\
              <li><a role='menuitem' tabindex='-1' href='javascript:;' value='week'>每星期</a></li>\
              <li><a role='menuitem' tabindex='-1' href='javascript:;' value='month'>每月</a></li>\
            </ul>\
          </div>\
          <div class='ptime pull-left'>\
            <div class='dropdown planweek pull-left mr20'>\
              <button class='btn btn-default dropdown-toggle' type='button' id='excode' data-toggle='dropdown'>\
                <b val='0'>" + weekArray[parseInt(value.week || '0')] + "</b>\
                <span class='caret'></span>\
              </button>\
              <ul class='dropdown-menu' role='menu' aria-labelledby='excode'>\
                <li><a role='menuitem' tabindex='-1' href='javascript:;' value='1'>周一</a></li>\
                <li><a role='menuitem' tabindex='-1' href='javascript:;' value='2'>周二</a></li>\
                <li><a role='menuitem' tabindex='-1' href='javascript:;' value='3'>周三</a></li>\
                <li><a role='menuitem' tabindex='-1' href='javascript:;' value='4'>周四</a></li>\
                <li><a role='menuitem' tabindex='-1' href='javascript:;' value='5'>周五</a></li>\
                <li><a role='menuitem' tabindex='-1' href='javascript:;' value='6'>周六</a></li>\
                <li><a role='menuitem' tabindex='-1' href='javascript:;' value='0'>周日</a></li>\
              </ul>\
            </div>\
            <div class='plan_hms pull-left mr20 bt-input-text'>\
              <span><input type='number' name='hour' value='" + (value.hour || 0) + "' maxlength='2' max='23' min='0'></span>\
              <span class='name'>小时</span>\
            </div>\
            <div class='plan_hms pull-left mr20 bt-input-text'>\
              <span><input type='number' name='minute' value='" + (value.minute || 0) + "' maxlength='2' max='59' min='0'></span>\
              <span class='name'>分钟</span>\
            </div>\
          </div>\
        </div>\
        <form class='set-Config' action='/crontab/add' enctype='multipart/form-data' method='post' style='display: none;'>\
          <input type='text' name='type' value='' />\
          <input type='number' name='where1' value='' />\
          <input type='number' name='hour' value='' />\
          <input type='number' name='minute' value='' />\
          <input type='text' name='week' value='' />\
          <input type='submit' />\
        </form>\
      </div>" 
      $(this).append(html)
      this.initDropdown();
      return this;
    },

    initDropdown: function() {
      var that = this;
      $(this).find(".dropdown ul li a").click(function() {
        var txt = $(this).text();
        var type = $(this).attr("value");
        $(this).parents(".dropdown").find("button b").text(txt).attr("val",type);
        that.handleStypeChange(type);
      });
      if(this.reportCycleValue.type) {
        this.handleStypeChange(this.reportCycleValue.type);
      }
    },

    getCronSelectorData: function() {
      var type = $(this).find(".plancycle").find("b").attr("val");
      $(this).find(".set-Config input[name='type']").val(type);

      var is1;
      var is2 = 1;
      switch(type){
        case 'day-n':
          is1=31;
          break;
        case 'hour-n':
          is1=23;
          break;
        case 'minute-n':
          is1=59;
          break;
        case 'month':
          is1=31;
          break;
      }
      
      var where1 = $(this).find('.excode_week b').attr('val');
      $(this).find(".set-Config input[name='where1']").val(where1);

      // if(where1 > is1 || where1 < is2){
      // 	$(this).find(".ptime input[name='where1']").focus();
      // 	layer.msg('表单不合法,请重新输入!',{icon:2});
      // 	return;
      // }
      
      var hour = $(this).find(".ptime input[name='hour']").val();
      if(hour > 23 || hour < 0){
        $(this).find(".ptime input[name='hour']").focus();
        layer.msg('小时值不合法!',{icon:2});
        return;
      }
      $(this).find(".set-Config input[name='hour']").val(hour);
      var minute = $(this).find(".ptime input[name='minute']").val();
      if(minute > 59 || minute < 0){
        $(this).find(".ptime input[name='minute']").focus();
        layer.msg('分钟值不合法!',{icon:2});
        return;
      }
      $(this).find(".set-Config input[name='minute']").val(minute);
      
      if (type == 'minute-n'){
        var where1 = $(this).find(".ptime input[name='where1']").val();
        $(this).find(".set-Config input[name='where1']").val(where1);
      }

      if (type == 'day-n'){
        var where1 = $(this).find(".ptime input[name='where1']").val();
        $(this).find(".set-Config input[name='where1']").val(where1);
      }

      if (type == 'hour-n'){
        var where1 = $(this).find(".ptime input[name='where1']").val();
        $(this).find(".set-Config input[name='where1']").val(where1);
      }

      if (type == 'week'){
        // TODO 星期暂时写死0，待完善逻辑
        // var where1 = $("#ptime input[name='where1']").val();
        var where1 = 0;
        $(this).find(".set-Config input[name='where1']").val(where1);
      }
      let data = $(this).find(".set-Config").serialize();
      console.log("获取的值:", data)
      return data;
    },

    getselectname: function(){
      $(this).find(".dropdown ul li a").click(function(){
        var txt = $(this).text();
        var type = $(this).attr("value");
        $(this).parents(".dropdown").find("button b").text(txt).attr("val",type);
      });
    },
    
    //清理
    closeOpt: function(){
      $(this).find(".ptime").html('');
    },

    //星期
    toWeek: function(){
      var mBody = '<div class="dropdown planweek pull-left mr20">\
              <button class="excode_week btn btn-default dropdown-toggle" type="button" data-toggle="dropdown">\
              <b val="0">' + weekArray[parseInt(this.reportCycleValue.week || '0')] + '</b> <span class="caret"></span>\
              </button>\
              <ul class="dropdown-menu" role="menu" aria-labelledby="excode_week">\
              <li><a role="menuitem" tabindex="-1" href="javascript:;" value="1">周一</a></li>\
              <li><a role="menuitem" tabindex="-1" href="javascript:;" value="2">周二</a></li>\
              <li><a role="menuitem" tabindex="-1" href="javascript:;" value="3">周三</a></li>\
              <li><a role="menuitem" tabindex="-1" href="javascript:;" value="4">周四</a></li>\
              <li><a role="menuitem" tabindex="-1" href="javascript:;" value="5">周五</a></li>\
              <li><a role="menuitem" tabindex="-1" href="javascript:;" value="6">周六</a></li>\
              <li><a role="menuitem" tabindex="-1" href="javascript:;" value="0">周日</a></li>\
              </ul>\
            </div>';
      $(this).find(".ptime").html(mBody);
      this.getselectname();
    },

    //指定1
    toWhere1: function(ix){
      var mBody ='<div class="plan_hms pull-left mr20 bt-input-text">\
              <span><input type="number" name="where1" value="' + (this.reportCycleValue.where1 || 3) + '" maxlength="2" max="31" min="0"></span>\
              <span class="name">'+ix+'</span>\
            </div>';
      $(this).find(".ptime").append(mBody);
    }, 

    //小时
    toHour: function(){
      var mBody = '<div class="plan_hms pull-left mr20 bt-input-text">\
              <span><input type="number" name="hour" value="' + (this.reportCycleValue.hour || 0) + '" maxlength="2" max="23" min="0"></span>\
              <span class="name">小时</span>\
              </div>';
      $(this).find(".ptime").append(mBody);
    },

    //分钟
    toMinute: function(){
      var mBody = '<div class="plan_hms pull-left mr20 bt-input-text">\
              <span><input type="number" name="minute" value="' + (this.reportCycleValue.minute || 0) + '" maxlength="2" max="59" min="0"></span>\
              <span class="name">分钟</span>\
              </div>';
      $(this).find(".ptime").append(mBody);	
    },

    handleStypeChange: function(type){
      switch(type){
        case 'day':
          this.closeOpt();
          this.toHour();
          this.toMinute();
          break;
        case 'day-n':
          this.closeOpt();
          this.toWhere1('天');
          this.toHour();
          this.toMinute();
          break;
        case 'hour':
          this.closeOpt();
          this.toMinute();
          break;
        case 'hour-n':
          this.closeOpt();
          this.toWhere1('小时');
          this.toMinute();
          break;
        case 'minute-n':
          this.closeOpt();
          this.toWhere1('分钟');
          break;
        case 'week':
          this.closeOpt();
          this.toWeek();
          this.toHour();
          this.toMinute();
          break;
        case 'month':
          this.closeOpt();
          this.toWhere1('日');
          this.toHour();
          this.toMinute();
          break;
      }
    }
  })
})()


createCronSelector