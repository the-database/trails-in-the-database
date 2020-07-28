import React from 'react';

import jpnFlag from './img/jpn.png';
import usaFlag from './img/usa.png';

import skyFcLogo from './img/skyfc.png';
import skyScLogo from './img/skysc.png';
import sky3rdLogo from './img/sky3rd.png';

import zeroLogo from './img/zero.png';
import aoLogo from './img/ao.png';

import senLogo from './img/cs.png';
import seniiLogo from './img/cs2.png';
import seniiiLogo from './img/seniii.png';
import senivLogo from './img/seniv.png';

import hajimariLogo from './img/hajimari.png';

const ReleaseInfo = () => (
  <div className="container">
    <h2>Release Info</h2>
    <table className="table">
      <tbody>
        <tr>
          <th>1</th>
          <td rowSpan="3" style={{background:'#337ab7', borderColor: '#2e6da4', padding: '10px 5px', color: 'white', textAlign: 'center', verticalAlign: 'middle'}}>VI</td>
          <td><img alt="" className="logo" style={{maxHeight: 50, maxWidth: 80}} src={skyFcLogo}/></td>
          <th>Trails in the Sky
    <small style={{color:'rgba(0,0,0,.5)', display: 'block', fontWeight:'normal'}}>空の軌跡FC ・ Sora no Kiseki FC</small>
          </th>
          <td>
            <span style={{fontWeight: 'normal'}}>
              <img alt="" className="flag" src={jpnFlag}/> <strong>2004/06/24</strong> (PC) ・ <small>2006/09/28 (PSP) ・ 2012/12/13 (PS3) ・ 2015/06/11 (PS Vita)</small>
              <br/>
              <img alt="" className="flag" src={usaFlag}/> <strong>2011/03/29</strong> (PSP) ・ <small>2014/07/29 (PC)</small>
            </span>
          </td>
        </tr>
        <tr>
          <th>2</th>
          <td><img alt="" className="logo" style={{maxHeight: 50, maxWidth: 80}} src={skyScLogo}/></td>
          <th>Trails in the Sky SC
    <small style={{color:'rgba(0,0,0,.5)', display: 'block', fontWeight:'normal'}}>空の軌跡SC ・ Sora no Kiseki SC</small>
          </th>
          <td>
              <span style={{fontWeight: 'normal'}}>
              <img alt="" className="flag" src={jpnFlag}/> <strong>2006/03/09</strong> (PC) ・ <small>2007/09/27 (PSP) ・ 2013/04/25 (PS3) ・ 2015/12/10 (PS Vita)</small>
              <br/>
              <img alt="" className="flag" src={usaFlag}/> <strong>2015/10/29</strong> (PC, PSP)
            </span>
          </td>
        </tr>
        <tr>
          <th>3</th>
          <td><img alt="" className="logo" style={{maxHeight: 50, maxWidth: 80}} src={sky3rdLogo}/></td>
          <th>Trails in the Sky the 3rd
    <small style={{color:'rgba(0,0,0,.5)', display: 'block', fontWeight:'normal'}}>空の軌跡 the 3rd ・ Sora no Kiseki the 3rd</small>
          </th>
          <td>
            <span style={{fontWeight: 'normal'}}>
              <img alt="" className="flag" src={jpnFlag}/> <strong>2007/06/28</strong> (PC) ・ <small>2008/07/24 (PSP) ・ 2013/06/27 (PS3) ・ 2016/07/14 (PS Vita)</small>
              <br/>
              <img alt="" className="flag" src={usaFlag}/> <strong>2017/05/03</strong> (PC)
            </span>
          </td>
        </tr>
        <tr>
          <th>4</th>
          <td rowSpan="2" style={{background: '#5bc0de', borderColor: '#4cae4c', padding: '10px 5px', color: 'white', textAlign: 'center', verticalAlign:'middle'}}>VII</td>
          <td><img alt="" className="logo" style={{maxHeight: 50, maxWidth: 80}} src={zeroLogo}/></td>
          <th>Trails from Zero
    <small style={{color:'rgba(0,0,0,.5)', display: 'block', fontWeight:'normal'}}>零の軌跡 ・ Zero no Kiseki</small>
          </th>
          <td>
            <span style={{fontWeight: 'normal'}}>
              <img alt="" className="flag" src={jpnFlag}/> <strong>2010/09/30</strong> (PSP) ・ <small>2012/10/18 (PS Vita) ・ 2013/06/14 (PC)</small> ・ <small>2020/04/23 (PS4)</small>
              <br/>
              <img alt="" className="flag" src={usaFlag}/> -
            </span>
          </td>
        </tr>
        <tr>
          <th>5</th>
          <td><img alt="" className="logo" style={{maxHeight: 50, maxWidth: 80}} src={aoLogo}/></td>
          <th>Trails to Azure
    <small style={{color:'rgba(0,0,0,.5)', display: 'block', fontWeight:'normal'}}>碧の軌跡 ・ Ao no Kiseki</small>
          </th>
          <td>
            <span style={{fontWeight: 'normal'}}>
              <img alt="" className="flag" src={jpnFlag}/> <strong>2011/09/29</strong> (PSP) ・ <small>2014/06/12 (PS Vita)</small> ・ <small>2020/05/28 (PS4)</small>
              <br/>
              <img alt="" className="flag" src={usaFlag}/> -
            </span>
          </td>
        </tr>
        <tr>
          <th>6</th>
          <td rowSpan="4" style={{background: '#d9534f',  borderColor: '#d43f3a', padding: '10px 5px', color: 'white', textAlign: 'center', verticalAlign:'middle'}}>VIII</td>
          <td><img alt="" className="logo" style={{maxHeight: 50, maxWidth: 80}} src={senLogo}/></td>
          <th>Trails of Cold Steel
    <small style={{color:'rgba(0,0,0,.5)', display: 'block', fontWeight:'normal'}}>閃の軌跡 ・ Sen no Kiseki</small>
          </th>
          <td>
            <span style={{fontWeight: 'normal'}}>
              <img alt="" className="flag" src={jpnFlag}/> <strong>2013/09/26</strong> (PS3, PS Vita) ・ <small>2017/08/02 (PC)</small> ・ <small>2018/03/08 (PS4)</small>
              <br/>
              <img alt="" className="flag" src={usaFlag}/> <strong>2015/12/22</strong> (PS3, PS Vita) ・ <small>2017/08/02 (PC)</small>
            </span>
          </td>
        </tr>
        <tr>
          <th>7</th>
          <td><img alt="" className="logo" style={{maxHeight: 50, maxWidth: 80}} src={seniiLogo}/></td>
          <th>Trails of Cold Steel II
    <small style={{color:'rgba(0,0,0,.5)', display: 'block', fontWeight:'normal'}}>閃の軌跡II ・ Sen no Kiseki II</small>
          </th>
          <td>
            <span style={{fontWeight: 'normal'}}>
              <img alt="" className="flag" src={jpnFlag}/> <strong>2014/09/25</strong> (PS3, PS Vita) ・ <small>2018/02/14 (PC)</small> ・ <small>2018/04/26 (PS4)</small>
              <br/>
              <img alt="" className="flag" src={usaFlag}/> <strong>2016/09/06</strong> (PS3, PS Vita) ・ <small>2018/02/14 (PC)</small>
            </span>
          </td>
        </tr>
        <tr>
          <th>8</th>
          <td><img alt="" className="logo" style={{maxHeight: 50, maxWidth: 80}} src={seniiiLogo}/></td>
          <th>Trails of Cold Steel III
    <small style={{color:'rgba(0,0,0,.5)', display: 'block', fontWeight:'normal'}}>閃の軌跡III ・ Sen no Kiseki III</small>
          </th>
          <td>
            <span style={{fontWeight: 'normal'}}>
              <img alt="" className="flag" src={jpnFlag}/> <strong>2017/09/28</strong> (PS4) ・ <small>2020/03/19 (Switch)</small> ・ <small>2020/03/23 (PC)</small>
              <br/>
              <img alt="" className="flag" src={usaFlag}/> <strong>2019/10/22</strong> (PS4) ・ <small>2020/03/23 (PC)</small> ・ <small>2020/06/30 (Switch)</small>
            </span>
          </td>
        </tr>
        <tr>
          <th>9</th>
          <td><img alt="" className="logo" style={{maxHeight: 50, maxWidth: 80}} src={senivLogo}/></td>
          <th>Trails of Cold Steel IV
    <small style={{color:'rgba(0,0,0,.5)', display: 'block', fontWeight:'normal'}}>閃の軌跡IV ・ Sen no Kiseki IV</small>
          </th>
          <td>
            <span style={{fontWeight: 'normal'}}>
              <img alt="" className="flag" src={jpnFlag}/> <strong>2018/09/27</strong> (PS4)
              <br/>
              <img alt="" className="flag" src={usaFlag}/> <strong>2020/10/27</strong> (PS4) ・ <small>2021 (PC, Switch)</small>
            </span>
          </td>
        </tr>
        <tr>
          <th>10</th>
          <th></th>
          <td><img alt="" className="logo" style={{maxHeight: 50, maxWidth: 80}} src={hajimariLogo}/></td>
          <th>
    <small style={{color:'rgba(0,0,0,.5)', display: 'block', fontWeight:'normal'}}>創の軌跡 ・ Hajimari no Kiseki</small>
          </th>
          <td>
            <span style={{fontWeight: 'normal'}}>
              <img alt="" className="flag" src={jpnFlag}/> <strong>2020/08/27</strong> (PS4)
              <br/>
              <img alt="" className="flag" src={usaFlag}/> -
            </span>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
);

export default ReleaseInfo;