// SPDX-License-Identifier: GPL-3.0

pragma solidity >=0.7.0 <0.9.0;

/** 
 * @title AMLicense
 * @dev Stores license terms and completed prints
 */
contract AMLicense {
   
    struct Print {
        address approvedby;
        string reporthash;
    }

    struct License {
        address licensedby;
        address licensedto;
        uint numprints;
        string parthash;
        Print[] prints;
    }


    License[] public licenseList;
    mapping(uint256 => License) licenses;
    uint256 public licenseCount = 0;
    



    function addLicense(address _licensedto, uint _numprints, string memory _parthash) public returns (License memory){
        License storage new_license = licenses[licenseCount];
        new_license.licensedby = msg.sender;
        new_license.licensedto = _licensedto;
        new_license.parthash = _parthash;
        new_license.numprints = _numprints;

        licenseList.push(new_license);
        
        licenseCount++;
        
        return licenses[licenseCount-1];
    }


    function addPrint(uint _licenseid, string memory _reporthash) public returns (uint){
        require(licenses[_licenseid].prints.length < licenses[_licenseid].numprints, "Part quota already met for this license or license ID does not exist.");
        require((msg.sender == licenses[_licenseid].licensedby) || (msg.sender == licenses[_licenseid].licensedto), "You are not authorized to add prints to this license.");
        Print memory new_print = Print(msg.sender, _reporthash);
        licenses[_licenseid].prints.push(new_print);
        
        return licenses[_licenseid].prints.length;
    }
    
    
    function getLicense(uint _licenseid) public view returns (License memory) {
        require(_licenseid < licenseCount, "License ID does not exist.");
        return licenses[_licenseid];
    }
    
    
    function getPrint(uint _licenseid, uint _printid) public view returns (Print memory) {
        require(_licenseid < licenseCount, "License ID does not exist.");
        require(_printid < licenses[_licenseid].prints.length, "Print ID does not exist.");
        return licenses[_licenseid].prints[_printid];
    }
    
    
    function listLicenses() public view returns (License[] memory) {
        return licenseList;
    }
    
    
    function getLicenseCount() public view returns (uint){
        return licenseList.length;
    }
}
