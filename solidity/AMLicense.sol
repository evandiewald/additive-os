// SPDX-License-Identifier: GPL-3.0

pragma solidity >=0.7.0 <0.9.0;

/** 
 * @title AMLicense
 * @dev Stores license terms and completed prints
 */
contract AMLicense {
   
    struct Print {
        uint timestamp;
        uint operatorid;
        string reporthash;
    }

    struct License {
        address licensedby;
        address licensedfor;
        string parthash;
        uint numprints;
        Print[] prints;
    }


    License[] public licenses;
    uint256 public licenseCount = 0;


    function addLicense(address _licensedby, address _licensedfor, string memory _parthash, uint _numprints) public returns (uint){
        License storage new_license = licenses[licenseCount];
        new_license.licensedby = _licensedby;
        new_license.licensedfor = _licensedfor;
        new_license.parthash = _parthash;
        new_license.numprints = _numprints;
        
        licenses.push(new_license);
        
        licenseCount++;
        
        return licenses.length;
    }


    function addPrint(uint _licenseid, uint _timestamp, uint _operatorid, string memory _reporthash) public returns (uint){
        require(licenses[_licenseid].prints.length < licenses[_licenseid].numprints, "Part quota already met for this license.");
        Print memory new_print = Print(_timestamp, _operatorid, _reporthash);
        licenses[_licenseid].prints.push(new_print);
        
        return licenses[_licenseid].prints.length;
    }
    
    
    function getLicense(uint _licenseid) public view returns (License memory) {
        return licenses[_licenseid];
    }
    
    
    function getPrint(uint _licenseid, uint _printid) public view returns (Print memory) {
        return licenses[_licenseid].prints[_printid];
    }
}
